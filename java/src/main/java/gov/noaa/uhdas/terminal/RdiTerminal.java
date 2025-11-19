package gov.noaa.uhdas.terminal;

import gov.noaa.uhdas.serial.SerialPortManager;
import java.awt.EventQueue;
import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.logging.FileHandler;
import java.util.logging.Formatter;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;
import javax.swing.JFileChooser;
import javax.swing.JMenu;
import javax.swing.JMenuBar;
import javax.swing.JMenuItem;
import javax.swing.JOptionPane;

/**
 * Java clone of serial/rditerm.py built with Swing and NRJavaSerial.
 */
public class RdiTerminal extends SwingTerminal {
    private static final Logger LOGGER = Logger.getLogger(RdiTerminal.class.getName());
    private static final Map<Integer, Integer> RDI_BAUD_CODES = Map.of(
            300, 0,
            1200, 1,
            2400, 2,
            4800, 3,
            9600, 4,
            19200, 5,
            38400, 6,
            57600, 7,
            115200, 8);
    private static final Map<String, Integer> DEFAULT_DATA_BAUDS = Map.of(
            "BB", 38400,
            "WH", 115200,
            "Unrecognized", 9600);
    private static final DateTimeFormatter TS_FORMAT = DateTimeFormatter.ofPattern("yyMMddHHmmss")
            .withZone(ZoneOffset.UTC);

    private final Path dataDir;
    private final Path logDir;
    private final String prefix;
    private final String suffix;
    private String cruiseName;
    private String stacast;
    private String cmdFilename;
    private final String backupDir;
    private final int defaultBaud;
    private final Integer dataBaud;
    private String instrumentType = "";

    public RdiTerminal(String device,
                       int baud,
                       Integer dataBaud,
                       String prefix,
                       String suffix,
                       String cruiseName,
                       String stacast,
                       String cmdFilename,
                       String backupDir,
                       Path dataDir,
                       Path logDir) {
        super(new SerialPortManager(device, baud));
        this.defaultBaud = baud;
        this.dataBaud = dataBaud;
        this.prefix = prefix;
        this.suffix = suffix;
        this.cruiseName = cruiseName;
        this.stacast = stacast;
        this.cmdFilename = cmdFilename;
        this.backupDir = backupDir;
        this.dataDir = dataDir;
        this.logDir = logDir;
        configureLogger();
    }

    private void configureLogger() {
        try {
            Files.createDirectories(logDir);
            FileHandler handler = new FileHandler(logDir.resolve("rditerm.log").toString(), true);
            handler.setFormatter(new SimpleFormatter());
            LOGGER.addHandler(handler);
            LOGGER.setUseParentHandlers(false);
        } catch (IOException ex) {
            LOGGER.log(Level.WARNING, "Unable to create log directory", ex);
        }
    }

    private static class SimpleFormatter extends Formatter {
        @Override
        public String format(LogRecord record) {
            return String.format(Locale.US, "%1$tF %1$tT %2$s%n", record.getMillis(), record.getMessage());
        }
    }

    @Override
    protected void addCustomMenus(JMenuBar menuBar) {
        JMenu commandMenu = new JMenu("Command");
        commandMenu.add(menuItem("Wakeup", () -> wakeup()));
        commandMenu.add(menuItem("ZZZZ (go to sleep)", () -> sleep()));
        commandMenu.add(menuItem("Set Clock", () -> setClock()));
        commandMenu.add(menuItem("Send Setup", () -> askSendSetup()));
        commandMenu.add(menuItem("Show Config", () -> showConfig()));
        commandMenu.add(menuItem("Run Diagnostics", () -> runDiagnostics()));
        commandMenu.add(menuItem("Change to download Baud", () -> changeAllBaud(null)));
        commandMenu.add(menuItem("Start Binary", () -> startBinary(null)));
        commandMenu.add(menuItem("List Recorder Directory", () -> listRecorder()));
        commandMenu.add(menuItem("Erase Recorder NOW", () -> eraseRecorder()));
        menuBar.add(commandMenu);

        JMenu deployMenu = new JMenu("Deploy");
        deployMenu.add(menuItem("Deployment Initialization", () -> startDeployRecover()));
        deployMenu.add(menuItem("Set Clock", () -> setClock()));
        deployMenu.add(menuItem("Send Setup and Start", () -> askSendSetup()));
        deployMenu.add(menuItem("Send Setup and Start Without Asking", () -> noAskSendSetup()));
        menuBar.add(deployMenu);

        JMenu recoverMenu = new JMenu("Recover");
        recoverMenu.add(menuItem("Recovery Initialization", () -> startDeployRecover()));
        recoverMenu.add(menuItem("Download", () -> download()));
        menuBar.add(recoverMenu);
    }

    private JMenuItem menuItem(String title, Runnable action) {
        JMenuItem item = new JMenuItem(title);
        item.addActionListener(e -> action.run());
        return item;
    }

    private void wakeup() {
        try {
            startListening(false);
            setBaud(defaultBaud);
            clearBuffer();
            sendBreak(400);
            String banner = waitFor(">", Duration.ofSeconds(5));
            updateTypeFromBanner(banner);
        } catch (IOException | TimeoutException ex) {
            LOGGER.log(Level.WARNING, "Wakeup failed", ex);
            showError("Wakeup failed: " + ex.getMessage());
        }
    }

    private void updateTypeFromBanner(String banner) {
        if (banner.contains("WorkHorse")) {
            instrumentType = "WH";
        } else if (banner.contains("Broadband")) {
            instrumentType = "BB";
        } else {
            instrumentType = "Unrecognized";
        }
    }

    private void wakeIfSleeping() {
        if (instrumentType.isEmpty()) {
            wakeup();
            return;
        }
        try {
            startListening(false);
            sendLine("TS?");
            waitFor(">", Duration.ofSeconds(1));
        } catch (IOException | TimeoutException ex) {
            wakeup();
        }
    }

    private void setClock() {
        wakeIfSleeping();
        String ts = TS_FORMAT.format(Instant.now());
        try {
            sendLine("TS" + ts);
        } catch (IOException ex) {
            LOGGER.log(Level.SEVERE, "Unable to set clock", ex);
            showError("Unable to set clock: " + ex.getMessage());
        }
    }

    private void showConfig() {
        List<String> cmds = Arrays.asList("RA", "RS", "RB0", "PS3", "B?", "C?", "E?", "P?", "T?", "W?");
        try {
            sendCommands(cmds, Duration.ofSeconds(2));
        } catch (IOException | TimeoutException ex) {
            LOGGER.log(Level.SEVERE, "Unable to fetch config", ex);
            showError("Unable to fetch configuration: " + ex.getMessage());
        }
    }

    private void sendCommands(List<String> commands, Duration timeout) throws IOException, TimeoutException {
        Duration wait = timeout == null ? Duration.ofSeconds(2) : timeout;
        startListening(false);
        for (String cmd : commands) {
            if (cmd == null || cmd.isBlank()) {
                continue;
            }
            sendLine(cmd.trim());
            waitFor(">", wait);
        }
    }

    private void runDiagnostics() {
        try {
            sendCommands(Arrays.asList("PS0", "PT200"), Duration.ofSeconds(2));
        } catch (IOException | TimeoutException ex) {
            LOGGER.log(Level.WARNING, "Diagnostics failed", ex);
            showError("Diagnostics failed: " + ex.getMessage());
        }
    }

    private void sleep() {
        try {
            setBaud(defaultBaud);
            wakeIfSleeping();
            sendLine("CZ");
            waitFor("Powering", Duration.ofSeconds(5));
        } catch (IOException | TimeoutException ex) {
            LOGGER.log(Level.WARNING, "Unable to put instrument to sleep", ex);
            showError("Unable to put instrument to sleep: " + ex.getMessage());
        }
    }

    private void eraseRecorder() {
        try {
            setBaud(defaultBaud);
            wakeIfSleeping();
            sendLine("RE ErAsE");
            waitFor(">", Duration.ofSeconds(5));
        } catch (IOException | TimeoutException ex) {
            LOGGER.log(Level.SEVERE, "Erase failed", ex);
            showError("Erase failed: " + ex.getMessage());
        }
    }

    private void changeAllBaud(Integer baud) {
        int newBaud = baud != null ? baud : getDataBaud();
        try {
            sendCommands(List.of(""), Duration.ofSeconds(2));
            sendLine(String.format("CB%d11", RDI_BAUD_CODES.getOrDefault(newBaud, 4)));
            waitFor(">", Duration.ofSeconds(3));
            setBaud(newBaud);
            Thread.sleep(500);
        } catch (IOException | TimeoutException | InterruptedException ex) {
            Thread.currentThread().interrupt();
            LOGGER.log(Level.WARNING, "Unable to change baud", ex);
            showError("Unable to change baud: " + ex.getMessage());
        }
    }

    private int getDataBaud() {
        if (dataBaud != null) {
            return dataBaud;
        }
        return DEFAULT_DATA_BAUDS.getOrDefault(instrumentType, defaultBaud);
    }

    private void listRecorder() {
        List<String> cmds = instrumentType.equals("BB") ? Arrays.asList("RA", "RS")
                : Arrays.asList("RA", "RS", "RF", "RR");
        try {
            sendCommands(cmds, Duration.ofSeconds(2));
        } catch (IOException | TimeoutException ex) {
            LOGGER.log(Level.WARNING, "Unable to list recorder", ex);
            showError("Unable to list recorder: " + ex.getMessage());
        }
    }

    private void startBinary(List<String> cmdlist) {
        try {
            wakeIfSleeping();
            setClock();
            if (cmdlist != null) {
                sendCommands(cmdlist, Duration.ofSeconds(2));
            }
            sendLine("CF11110");
        } catch (IOException | TimeoutException ex) {
            LOGGER.log(Level.SEVERE, "Unable to start binary mode", ex);
            showError("Unable to start binary mode: " + ex.getMessage());
        }
    }

    private void startDeployRecover() {
        clear();
        insert("***************************** " + Instant.now() + "\n");
        wakeup();
        listRecorder();
    }

    private void sendSetup() {
        wakeIfSleeping();
        Path path = Paths.get(cmdFilename);
        if (!Files.exists(path)) {
            showError("Command file not found: " + path);
            return;
        }
        try {
            insert("Sending command file: " + path + "\n");
            List<String> commands = readValidatedCommands(path);
            sendCommands(commands, Duration.ofSeconds(2));
            sendLine("CK");
            waitFor("Parameters saved", Duration.ofSeconds(2));
            sendLine("CS");
            insert("Data collection started at " + Instant.now() + "\n");
            appendDeploymentLog();
        } catch (IOException | TimeoutException ex) {
            LOGGER.log(Level.SEVERE, "Unable to send setup", ex);
            showError("Unable to send setup: " + ex.getMessage());
        }
    }

    private List<String> readValidatedCommands(Path path) throws IOException {
        List<String> cmds = new ArrayList<>();
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = stripComments(line);
                if (!line.isBlank() && !line.startsWith("CK") && !line.startsWith("CS")) {
                    cmds.add(line.trim());
                }
            }
        }
        return cmds;
    }

    private String stripComments(String line) {
        String cleaned = line.split("#", 2)[0];
        cleaned = cleaned.split(";", 2)[0];
        cleaned = cleaned.split("\\$", 2)[0];
        return cleaned.trim();
    }

    private void appendDeploymentLog() throws IOException {
        Files.createDirectories(logDir);
        Path logFile = logDir.resolve(makeFilename(".log"));
        appendToFile(logFile);
        stopListening();
        try {
            startListening(true);
            insert("Deployment logfile written to " + logFile + "\n");
        } catch (IOException ex) {
            LOGGER.log(Level.WARNING, "Unable to restart listener", ex);
            showError("Unable to start logging to " + logFile + ": " + ex.getMessage());
        }
    }

    private void askSendSetup() {
        JFileChooser chooser = new JFileChooser();
        chooser.setDialogTitle("Command file");
        chooser.setSelectedFile(Paths.get(cmdFilename).toFile());
        if (chooser.showOpenDialog(this) == JFileChooser.APPROVE_OPTION) {
            cmdFilename = chooser.getSelectedFile().getAbsolutePath();
            sendSetup();
        }
    }

    private void noAskSendSetup() {
        Path path = Paths.get(cmdFilename);
        if (Files.exists(path)) {
            sendSetup();
        } else {
            askSendSetup();
        }
    }

    private void download() {
        JOptionPane.showMessageDialog(this,
                "YModem download is not implemented in the Java port yet.",
                "Download",
                JOptionPane.INFORMATION_MESSAGE);
    }

    private String makeFilename(String ext) {
        if (!ext.startsWith(".")) {
            ext = "." + ext;
        }
        return prefix + cruiseName + "_" + stacast + suffix + ext;
    }

    public static void main(String[] args) {
        CliOptions opts = CliOptions.parse(args);
        EventQueue.invokeLater(() -> {
            RdiTerminal terminal = new RdiTerminal(
                    opts.device,
                    opts.baud,
                    opts.dataBaud,
                    opts.prefix,
                    opts.suffix,
                    opts.cruiseName,
                    opts.stacast,
                    opts.cmdFilename,
                    opts.backupDir,
                    opts.dataDir,
                    opts.logDir);
            terminal.setVisible(true);
        });
    }

    private static class CliOptions {
        final String device;
        final int baud;
        final Integer dataBaud;
        final String prefix;
        final String suffix;
        final String cruiseName;
        final String stacast;
        final String cmdFilename;
        final String backupDir;
        final Path dataDir;
        final Path logDir;

        private CliOptions(String device, int baud, Integer dataBaud, String prefix, String suffix,
                            String cruiseName, String stacast, String cmdFilename, String backupDir,
                            Path dataDir, Path logDir) {
            this.device = device;
            this.baud = baud;
            this.dataBaud = dataBaud;
            this.prefix = prefix;
            this.suffix = suffix;
            this.cruiseName = cruiseName;
            this.stacast = stacast;
            this.cmdFilename = cmdFilename;
            this.backupDir = backupDir;
            this.dataDir = dataDir;
            this.logDir = logDir;
        }

        static CliOptions parse(String[] args) {
            Map<String, String> map = new HashMap<>();
            for (int i = 0; i < args.length - 1; i += 2) {
                if (args[i].startsWith("-")) {
                    map.put(args[i], args[i + 1]);
                }
            }
            String device = map.getOrDefault("-d", map.getOrDefault("--device", "/dev/ttyS0"));
            int baud = Integer.parseInt(map.getOrDefault("--baud", "9600"));
            Integer dataBaud = map.containsKey("--download") ? Integer.parseInt(map.get("--download")) : null;
            String prefix = map.getOrDefault("--prefix", "rdi");
            String suffix = map.getOrDefault("--suffix", "rdi");
            String cruiseName = map.getOrDefault("--cruise", "XXNNNN");
            String stacast = map.getOrDefault("--stacast", "000_00");
            String cmdFile = map.getOrDefault("--command", "ladcp.cmd");
            String backupDir = map.getOrDefault("--backup", "");
            Path dataDir = Paths.get(map.getOrDefault("--dataDir", "."));
            Path logDir = Paths.get(map.getOrDefault("--logDir", "."));
            return new CliOptions(device, baud, dataBaud, prefix, suffix, cruiseName, stacast,
                    cmdFile, backupDir, dataDir, logDir);
        }
    }
}
