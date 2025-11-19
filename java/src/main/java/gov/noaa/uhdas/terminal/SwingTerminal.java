package gov.noaa.uhdas.terminal;

import gov.noaa.uhdas.serial.SerialPortManager;
import java.awt.BorderLayout;
import java.awt.EventQueue;
import java.awt.event.ActionEvent;
import java.awt.event.KeyAdapter;
import java.awt.event.KeyEvent;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
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
import javax.swing.JButton;
import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.JMenu;
import javax.swing.JMenuBar;
import javax.swing.JMenuItem;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingUtilities;
import javax.swing.WindowConstants;

/**
 * Swing based serial terminal that mimics the Python Tk_terminal.
 */
public class SwingTerminal extends JFrame {
    private static final Logger LOGGER = Logger.getLogger(SwingTerminal.class.getName());

    protected final SerialPortManager port;
    protected final JTextArea display;
    protected final JTextField inputField;

    private final ExecutorService readerExecutor = Executors.newSingleThreadExecutor();
    private Future<?> readerFuture;
    private final AtomicBoolean listening = new AtomicBoolean(false);
    private boolean saveOutput;
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
        inputField.addActionListener(this::handleInput);
        inputField.addKeyListener(new HistoryListener());
        JPanel southPanel = new JPanel(new BorderLayout());
        southPanel.add(inputField, BorderLayout.CENTER);
        JButton sendButton = new JButton("Send");
        sendButton.addActionListener(this::handleInput);
        southPanel.add(sendButton, BorderLayout.EAST);
        setLayout(new BorderLayout());
        add(new JScrollPane(display), BorderLayout.CENTER);
        add(southPanel, BorderLayout.SOUTH);
        setJMenuBar(createMenuBar());
        pack();
        setLocationRelativeTo(null);
    }

    private JMenuBar createMenuBar() {
        JMenuBar menuBar = new JMenuBar();
        JMenu fileMenu = new JMenu("File");
        JMenuItem saveItem = new JMenuItem("Save display as...");
        saveItem.addActionListener(e -> saveDisplayToFile());
        JMenuItem clearItem = new JMenuItem("Clear");
        clearItem.addActionListener(e -> clear());
        JMenuItem exitItem = new JMenuItem("Exit");
        exitItem.addActionListener(e -> dispose());
        fileMenu.add(saveItem);
        fileMenu.add(clearItem);
        fileMenu.add(exitItem);
        menuBar.add(fileMenu);
        JMenu connectionMenu = new JMenu("Connection");
        JMenuItem listenItem = new JMenuItem("Start listening");
        listenItem.addActionListener(e -> safeStartListening());
        JMenuItem stopItem = new JMenuItem("Stop listening");
        stopItem.addActionListener(e -> stopListening());
        JMenuItem changeDeviceItem = new JMenuItem("Change device");
        changeDeviceItem.addActionListener(e -> changeDevice());
        connectionMenu.add(listenItem);
        connectionMenu.add(stopItem);
        connectionMenu.add(changeDeviceItem);
        menuBar.add(connectionMenu);
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
            } catch (IOException ex) {
                LOGGER.log(Level.SEVERE, "Unable to change device", ex);
                showError("Unable to change device: " + ex.getMessage());
            }
        }
    }

    private void safeStartListening() {
        try {
            startListening(true);
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
        listening.set(true);
        readerFuture = readerExecutor.submit(this::readLoop);
    }

    public void stopListening() {
        listening.set(false);
        if (readerFuture != null) {
            readerFuture.cancel(true);
        }
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
