package gov.noaa.uhdas.serial;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Optional;

/**
 * Lock file management modeled after the Python sp_lock module.
 */
public final class SerialLock {
    private static final Path LOCK_DIR = Paths.get("/var/lock");

    private SerialLock() {
    }

    private static Path lockFile(String device) {
        String baseName = device.replaceAll("^.+/", "");
        return LOCK_DIR.resolve("LCK.." + baseName);
    }

    public static synchronized void lock(String device) throws IOException {
        Path lockFile = lockFile(device);
        long currentPid = ProcessHandle.current().pid();
        if (Files.exists(lockFile)) {
            long existingPid = readPid(lockFile).orElse(-1L);
            if (existingPid == currentPid) {
                return; // already locked by this process
            }
            if (existingPid > 0 && ProcessHandle.of(existingPid).isPresent()) {
                throw new IllegalStateException(
                        String.format("Device %s is locked by pid %d", device, existingPid));
            }
            Files.delete(lockFile);
        }
        Files.createDirectories(LOCK_DIR);
        try (BufferedWriter writer = Files.newBufferedWriter(lockFile, StandardCharsets.UTF_8)) {
            writer.write(Long.toString(currentPid));
            writer.newLine();
        }
    }

    public static synchronized void unlock(String device) throws IOException {
        Path lockFile = lockFile(device);
        if (Files.exists(lockFile)) {
            Files.delete(lockFile);
        }
    }

    private static Optional<Long> readPid(Path lockFile) {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(Files.newInputStream(lockFile), StandardCharsets.UTF_8))) {
            String line = reader.readLine();
            if (line == null) {
                return Optional.empty();
            }
            return Optional.of(Long.parseLong(line.trim()));
        } catch (IOException | NumberFormatException ex) {
            return Optional.empty();
        }
    }
}
