package gov.noaa.uhdas.terminal;

import gov.noaa.uhdas.serial.SerialPortManager;
import java.awt.BorderLayout;
import java.awt.EventQueue;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.awt.event.ActionEvent;
import java.awt.event.KeyAdapter;
import java.awt.event.KeyEvent;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.logging.Level;
import java.util.logging.Logger;
import javax.swing.ButtonGroup;
import javax.swing.JButton;
import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JMenu;
import javax.swing.JMenuBar;
import javax.swing.JMenuItem;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JRadioButtonMenuItem;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.JToggleButton;
import javax.swing.SwingUtilities;
import javax.swing.WindowConstants;

/**
 * Swing based serial terminal that mimics the Python Tk_terminal.
 */
public class SwingTerminal extends JFrame {
    private static final Logger LOGGER = Logger.getLogger(SwingTerminal.class.getName());
    private static final int[] BAUD_RATES = new int[]{300, 600, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200};

    protected final SerialPortManager port;
    protected final JTextArea display;
    protected final JTextField inputField;
    protected final JLabel statusLabel;

    private final JMenuItem connectItem;
    private final JMenuItem disconnectItem;
    private final JMenuItem saveIncomingItem;
    private final JMenuItem stopSavingItem;
    private final JMenuItem clearItem;
    private final JMenuItem sendBreakItem;
    private final ButtonGroup baudGroup = new ButtonGroup();

    private final ExecutorService readerExecutor = Executors.newSingleThreadExecutor();
    private Future<?> readerFuture;
    private final AtomicBoolean listening = new AtomicBoolean(false);
    private boolean saveOutput;
    private boolean saveRequested;
    private Path incomingLog = Paths.get("term_diary.txt");
    private BufferedWriter appendWriter;
    private final Object bufferLock = new Object();
    private final StringBuilder buffer = new StringBuilder();
    private final List<String> history = new ArrayList<>();
    private int historyIndex = -1;

    public SwingTerminal(SerialPortManager port) {
        this.port = Objects.requireNonNull(port, "port");
        setTitle("LADCP Serial Terminal");
        setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);
        display = new JTextArea(30, 90);
        display.setEditable(false);
        inputField = new JTextField();
        inputField.setEnabled(false);
        inputField.addActionListener(this::handleInput);
        inputField.addKeyListener(new HistoryListener());

        JMenuBar menuBar = createMenuBar();
        connectItem = menuBar.getMenu(0).getItem(0);
        disconnectItem = menuBar.getMenu(0).getItem(1);
        saveIncomingItem = menuBar.getMenu(0).getItem(2);
        stopSavingItem = menuBar.getMenu(0).getItem(3);
        clearItem = menuBar.getMenu(0).getItem(5);
        sendBreakItem = menuBar.getMenu(3).getItem(0);
        setJMenuBar(menuBar);

        JPanel content = new JPanel(new BorderLayout());
        content.add(buildTopPanel(), BorderLayout.NORTH);
        content.add(new JScrollPane(display), BorderLayout.CENTER);
        content.add(buildTransmitPanel(), BorderLayout.SOUTH);
        setContentPane(content);
        updateMenuState();
        pack();
        setLocationRelativeTo(null);
    }

    private JPanel buildTopPanel() {
        JPanel top = new JPanel(new GridBagLayout());
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.gridx = 0;
        gbc.gridy = 0;
        gbc.anchor = GridBagConstraints.WEST;
        gbc.insets = new Insets(5, 5, 5, 5);
        JPanel statusPanel = new JPanel(new BorderLayout());
        statusPanel.add(new JLabel("Status:"), BorderLayout.WEST);
        statusLabel = new JLabel();
        statusPanel.add(statusLabel, BorderLayout.CENTER);
        top.add(statusPanel, gbc);
        setStatus(null);
        return top;
    }

    private JPanel buildTransmitPanel() {
        JPanel panel = new JPanel(new BorderLayout(5, 5));
        panel.add(new JLabel("Transmit line:"), BorderLayout.WEST);
        panel.add(inputField, BorderLayout.CENTER);
        JButton sendButton = new JButton("Send");
        sendButton.addActionListener(this::handleInput);
        panel.add(sendButton, BorderLayout.EAST);
        return panel;
    }

    private JMenuBar createMenuBar() {
        JMenuBar menuBar = new JMenuBar();
        JMenu fileMenu = new JMenu("File");
        JMenuItem connectMenu = new JMenuItem("Connect to port");
        connectMenu.addActionListener(e -> safeStartListening(false));
        JMenuItem disconnectMenu = new JMenuItem("Disconnect");
        disconnectMenu.addActionListener(e -> stopListening());
        JMenuItem saveIncomingMenu = new JMenuItem("Save incoming");
        saveIncomingMenu.addActionListener(e -> chooseIncomingLog());
        JMenuItem stopSavingMenu = new JMenuItem("Stop saving");
        stopSavingMenu.addActionListener(e -> stopSaving());
        JMenuItem savePrevMenu = new JMenuItem("Save previous");
        savePrevMenu.addActionListener(e -> saveDisplayToFile());
        JMenuItem clearMenu = new JMenuItem("Clear");
        clearMenu.addActionListener(e -> clear());
        JMenuItem quitMenu = new JMenuItem("Quit");
        quitMenu.addActionListener(e -> dispose());
        fileMenu.add(connectMenu);
        fileMenu.add(disconnectMenu);
        fileMenu.add(saveIncomingMenu);
        fileMenu.add(stopSavingMenu);
        fileMenu.add(savePrevMenu);
        fileMenu.add(clearMenu);
        fileMenu.add(quitMenu);
        menuBar.add(fileMenu);

        JMenu baudMenu = new JMenu("Baud");
        for (int baud : BAUD_RATES) {
            JToggleButton.ToggleButtonModel model = new JToggleButton.ToggleButtonModel();
            model.setActionCommand(String.valueOf(baud));
            JMenuItem baudItem = new JRadioButtonMenuItemWithModel(model, String.valueOf(baud));
            baudGroup.add(baudItem);
            baudItem.addActionListener(e -> changeBaud(Integer.parseInt(e.getActionCommand())));
            if (baud == port.getBaudRate()) {
                model.setSelected(true);
            }
            baudMenu.add(baudItem);
        }
        menuBar.add(baudMenu);

        JMenu portMenu = new JMenu("Port");
        JMenuItem deviceMenu = new JMenuItem("Device");
        deviceMenu.addActionListener(e -> changeDevice());
        JMenuItem viewSetMenu = new JMenuItem("View/Set");
        viewSetMenu.addActionListener(e -> showUnsupported());
        portMenu.add(deviceMenu);
        portMenu.add(viewSetMenu);
        menuBar.add(portMenu);

        JMenu commandMenu = new JMenu("Command");
        JMenuItem sendBreakMenu = new JMenuItem("Send Break");
        sendBreakMenu.addActionListener(e -> sendBreakSafe());
        commandMenu.add(sendBreakMenu);
        menuBar.add(commandMenu);
        addCustomMenus(menuBar);
        return menuBar;
    }

    protected void addCustomMenus(JMenuBar menuBar) {
        // subclasses override
    }

    private void changeDevice() {
        String newDevice = JOptionPane.showInputDialog(this, "Serial device", port.getDevice());
        if (newDevice != null && !newDevice.isBlank()) {
            try {
                port.changeDevice(newDevice.trim());
                setStatus(null);
            } catch (IOException ex) {
                LOGGER.log(Level.SEVERE, "Unable to change device", ex);
                showError("Unable to change device: " + ex.getMessage());
            }
        }
    }

    private void safeStartListening(boolean forceSave) {
        try {
            startListening(forceSave || saveRequested);
        } catch (IOException ex) {
            LOGGER.log(Level.SEVERE, "Unable to open serial port", ex);
            showError("Unable to open serial port: " + ex.getMessage());
        }
    }

    public void startListening(boolean save) throws IOException {
        if (listening.get()) {
            return;
        }
        port.open();
        saveOutput = save;
        if (saveOutput) {
            beginSaving();
        }
        listening.set(true);
        inputField.setEnabled(true);
        readerFuture = readerExecutor.submit(this::readLoop);
        updateMenuState();
        setStatus(null);
    }

    public void stopListening() {
        listening.set(false);
        if (readerFuture != null) {
            readerFuture.cancel(true);
        }
        endSaving();
        saveRequested = false;
        inputField.setEnabled(false);
        updateMenuState();
        setStatus(null);
    }

    private void readLoop() {
        byte[] buffer = new byte[2048];
        while (listening.get()) {
            try {
                int read = port.read(buffer);
                if (read > 0) {
                    String text = new String(buffer, 0, read, StandardCharsets.US_ASCII);
                    appendText(text);
                    if (saveOutput && appendWriter != null) {
                        appendWriter.write(text);
                        appendWriter.flush();
                    }
                }
            } catch (IOException ex) {
                LOGGER.log(Level.WARNING, "Serial read failure", ex);
                showError("Serial read failure: " + ex.getMessage());
                listening.set(false);
            }
        }
    }

    protected void appendText(String text) {
        synchronized (bufferLock) {
            buffer.append(text);
            if (buffer.length() > 16384) {
                buffer.delete(0, buffer.length() - 16384);
            }
        }
        SwingUtilities.invokeLater(() -> display.append(text));
    }

    public void clear() {
        synchronized (bufferLock) {
            buffer.setLength(0);
        }
        SwingUtilities.invokeLater(() -> display.setText(""));
    }

    public String waitFor(String token, Duration timeout) throws TimeoutException {
        long deadline = System.nanoTime() + timeout.toNanos();
        while (System.nanoTime() < deadline) {
            synchronized (bufferLock) {
                int idx = buffer.indexOf(token);
                if (idx >= 0) {
                    return buffer.substring(0, idx + token.length());
                }
            }
            try {
                Thread.sleep(50);
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                throw new TimeoutException("Interrupted while waiting for " + token);
            }
        }
        throw new TimeoutException("Timed out waiting for " + token);
    }

    public void appendToFile(Path path) throws IOException {
        if (appendWriter != null) {
            appendWriter.close();
        }
        if (path.getParent() != null) {
            Files.createDirectories(path.getParent());
        }
        appendWriter = Files.newBufferedWriter(path, StandardCharsets.UTF_8);
    }

    public void insert(String msg) {
        appendText(msg);
    }

    public void sendLine(String command) throws IOException {
        port.write((command + "\r").getBytes(StandardCharsets.US_ASCII));
    }

    public void sendBytes(byte[] data) throws IOException {
        port.write(data);
    }

    public void sendBreak(int milliseconds) throws IOException {
        port.sendBreak(milliseconds);
    }

    public void setBaud(int baud) throws IOException {
        port.setBaudRate(baud);
    }

    public void clearBuffer() {
        synchronized (bufferLock) {
            buffer.setLength(0);
        }
    }

    public String getLineContaining(String token) {
        synchronized (bufferLock) {
            String[] lines = buffer.toString().split("\n");
            for (int i = lines.length - 1; i >= 0; i--) {
                if (lines[i].contains(token)) {
                    return lines[i];
                }
            }
        }
        return "";
    }

    public String getLinesFrom(String token) {
        synchronized (bufferLock) {
            String[] lines = buffer.toString().split("\n");
            StringBuilder sb = new StringBuilder();
            boolean found = false;
            for (String line : lines) {
                if (!found && line.contains(token)) {
                    found = true;
                }
                if (found) {
                    sb.append(line).append('\n');
                }
            }
            return sb.toString();
        }
    }

    public void saveDisplayToFile() {
        JFileChooser chooser = new JFileChooser();
        if (chooser.showSaveDialog(this) == JFileChooser.APPROVE_OPTION) {
            Path path = chooser.getSelectedFile().toPath();
            try {
                Files.writeString(path, display.getText(), StandardCharsets.UTF_8);
            } catch (IOException ex) {
                showError("Unable to save file: " + ex.getMessage());
            }
        }
    }

    private void chooseIncomingLog() {
        JFileChooser chooser = new JFileChooser();
        chooser.setSelectedFile(incomingLog.toFile());
        if (chooser.showSaveDialog(this) == JFileChooser.APPROVE_OPTION) {
            incomingLog = chooser.getSelectedFile().toPath();
            saveRequested = true;
            if (listening.get()) {
                try {
                    beginSaving();
                } catch (IOException ex) {
                    LOGGER.log(Level.WARNING, "Unable to open log file", ex);
                    showError("Unable to open log file: " + ex.getMessage());
                }
            }
            updateMenuState();
        }
    }

    private void beginSaving() throws IOException {
        endSaving();
        appendToFile(incomingLog);
        saveOutput = true;
    }

    private void stopSaving() {
        saveRequested = false;
        saveOutput = false;
        endSaving();
        updateMenuState();
    }

    private void endSaving() {
        if (appendWriter != null) {
            try {
                appendWriter.flush();
                appendWriter.close();
            } catch (IOException ex) {
                LOGGER.log(Level.WARNING, "Unable to close log writer", ex);
            }
            appendWriter = null;
        }
    }

    private void handleInput(ActionEvent event) {
        String text = inputField.getText();
        if (text == null || text.isBlank()) {
            return;
        }
        try {
            sendLine(text);
            history.add(text);
            historyIndex = history.size();
        } catch (IOException ex) {
            LOGGER.log(Level.SEVERE, "Unable to send command", ex);
            showError("Unable to send command: " + ex.getMessage());
        } finally {
            inputField.setText("");
        }
    }

    public String getDisplayText() {
        return display.getText();
    }

    protected void showError(String message) {
        EventQueue.invokeLater(() -> JOptionPane.showMessageDialog(this, message, "Error",
                JOptionPane.ERROR_MESSAGE));
    }

    private void changeBaud(int baud) {
        try {
            port.setBaudRate(baud);
            setStatus(null);
        } catch (IOException ex) {
            LOGGER.log(Level.WARNING, "Unable to change baud", ex);
            showError("Unable to change baud: " + ex.getMessage());
        }
    }

    private void sendBreakSafe() {
        try {
            sendBreak(300);
        } catch (IOException ex) {
            LOGGER.log(Level.WARNING, "Unable to send break", ex);
            showError("Unable to send break: " + ex.getMessage());
        }
    }

    private void showUnsupported() {
        JOptionPane.showMessageDialog(this,
                "Viewing or setting serial flags is not available in the Java port.",
                "Port flags",
                JOptionPane.INFORMATION_MESSAGE);
    }

    private void updateMenuState() {
        boolean isListening = listening.get();
        connectItem.setEnabled(!isListening);
        disconnectItem.setEnabled(isListening);
        saveIncomingItem.setEnabled(!saveOutput);
        stopSavingItem.setEnabled(saveOutput);
        clearItem.setEnabled(true);
        sendBreakItem.setEnabled(isListening);
    }

    private void setStatus(String custom) {
        String status;
        if (custom != null) {
            status = custom;
        } else {
            String connected = listening.get() ? "connected." : "not connected.";
            status = String.format("Device %s, at %d Baud, is %s",
                    port.getDevice(), port.getBaudRate(), connected);
        }
        statusLabel.setText(status);
    }

    private static class JRadioButtonMenuItemWithModel extends JRadioButtonMenuItem {
        JRadioButtonMenuItemWithModel(JToggleButton.ToggleButtonModel model, String label) {
            super(label);
            setModel(model);
        }
    }

    private class HistoryListener extends KeyAdapter {
        @Override
        public void keyPressed(KeyEvent e) {
            if (history.isEmpty()) {
                return;
            }
            if (e.getKeyCode() == KeyEvent.VK_UP) {
                historyIndex = Math.max(0, historyIndex - 1);
                inputField.setText(history.get(historyIndex));
            } else if (e.getKeyCode() == KeyEvent.VK_DOWN) {
                historyIndex = Math.min(history.size(), historyIndex + 1);
                if (historyIndex == history.size()) {
                    inputField.setText("");
                } else {
                    inputField.setText(history.get(historyIndex));
                }
            }
        }
    }
}
