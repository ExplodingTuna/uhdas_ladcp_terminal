package gov.noaa.uhdas.serial;

import gnu.io.CommPort;
import gnu.io.CommPortIdentifier;
import gnu.io.SerialPort;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Minimal NRJavaSerial wrapper that mimics the Python serial_port class.
 */
public class SerialPortManager {
    private static final Logger LOGGER = Logger.getLogger(SerialPortManager.class.getName());

    private final String applicationName;
    private String device;
    private int baudRate;
    private SerialPort serialPort;
    private InputStream inputStream;
    private OutputStream outputStream;

    public SerialPortManager(String device, int baudRate) {
        this(device, baudRate, "ladcp-terminal");
    }

    public SerialPortManager(String device, int baudRate, String applicationName) {
        this.device = device;
        this.baudRate = baudRate;
        this.applicationName = applicationName;
    }

    public synchronized void open() throws IOException {
        if (serialPort != null) {
            return;
        }
        try {
            SerialLock.lock(device);
            CommPortIdentifier identifier = CommPortIdentifier.getPortIdentifier(device);
            CommPort commPort = identifier.open(applicationName, 2000);
            if (!(commPort instanceof SerialPort)) {
                throw new IOException("Device is not a serial port: " + device);
            }
            serialPort = (SerialPort) commPort;
            serialPort.setSerialPortParams(baudRate,
                    SerialPort.DATABITS_8,
                    SerialPort.STOPBITS_1,
                    SerialPort.PARITY_NONE);
            serialPort.enableReceiveTimeout(200);
            inputStream = serialPort.getInputStream();
            outputStream = serialPort.getOutputStream();
        } catch (Exception ex) {
            close();
            throw new IOException("Unable to open serial port " + device, ex);
        }
    }

    public synchronized void close() {
        if (serialPort != null) {
            try {
                inputStream.close();
            } catch (IOException ignored) {
            }
            try {
                outputStream.close();
            } catch (IOException ignored) {
            }
            serialPort.close();
            serialPort = null;
            inputStream = null;
            outputStream = null;
            try {
                SerialLock.unlock(device);
            } catch (IOException ex) {
                LOGGER.log(Level.WARNING, "Unable to remove lock file", ex);
            }
        }
    }

    public synchronized void changeDevice(String newDevice) throws IOException {
        if (newDevice.equals(device)) {
            return;
        }
        close();
        this.device = newDevice;
        open();
    }

    public synchronized void setBaudRate(int newBaudRate) throws IOException {
        this.baudRate = newBaudRate;
        if (serialPort == null) {
            return;
        }
        serialPort.setSerialPortParams(newBaudRate,
                serialPort.getDataBits(),
                serialPort.getStopBits(),
                serialPort.getParity());
    }

    public synchronized int getBaudRate() {
        return baudRate;
    }

    public synchronized String getDevice() {
        return device;
    }

    public synchronized void sendBreak(int durationMillis) throws IOException {
        if (serialPort == null) {
            open();
        }
        serialPort.sendBreak(durationMillis);
    }

    public synchronized void flush() throws IOException {
        if (outputStream != null) {
            outputStream.flush();
        }
    }

    public synchronized void write(byte[] data) throws IOException {
        if (serialPort == null) {
            open();
        }
        outputStream.write(data);
        outputStream.flush();
    }

    public synchronized void writeLine(String line) throws IOException {
        write((line + "\r").getBytes());
    }

    public synchronized int read(byte[] buffer) throws IOException {
        if (serialPort == null) {
            open();
        }
        return inputStream.read(buffer);
    }

    public synchronized InputStream getInputStream() throws IOException {
        if (serialPort == null) {
            open();
        }
        return inputStream;
    }

    public synchronized OutputStream getOutputStream() throws IOException {
        if (serialPort == null) {
            open();
        }
        return outputStream;
    }
}
