// =============================================================================
//  sim3-emulator.ino — make a microcontroller pretend to be the SIM3 chip
//
//  The SIM3 in the guide is an example design, not a part you can buy. This
//  sketch turns a small 3.3 V microcontroller board into an I2C "target"
//  (slave) at address 0x48 that behaves exactly like it, so you can test the
//  whole BMC side with real I2C traffic.
//
//  !! Use a 3.3 V board (Raspberry Pi Pico with arduino-pico, Arduino Nano
//  !! 33 IoT, Arduino Pro Mini 3.3 V, ESP32...). The BeagleBone's pins are
//  !! 3.3 V only; a 5 V Arduino Uno connected directly can damage it.
//
//  Registers:
//    0x00  TEMP    signed 8-bit, 1 °C per step
//    0x01  VOLT    unsigned 8-bit, 20 mV per step
//    0x02  STATUS  bit 0 = data ready, bit 1 = alert (temp > 50 °C), bit 7 = fault
//
//  How a read works on the wire (what "i2cget -y 2 0x48 0x01 b" does):
//    1. the BMC writes one byte, the register number   -> onReceive()
//    2. the BMC then reads one byte                    -> onRequest()
//
//  Serial monitor (115200 baud) commands, to test alarms:
//    h = make it hot (75 °C)   n = back to normal   f = toggle fault bit
// =============================================================================
#include <Wire.h>

const uint8_t I2C_ADDRESS = 0x48;

volatile uint8_t regs[3] = {25, 165, 0x01};  // 25 °C, 3.300 V, ready
volatile uint8_t selected = 0;               // register chosen by the last write
bool hot = false;
bool fault = false;

// Called when the BMC writes to us. The first byte is the register number.
void onReceive(int count) {
  if (count >= 1) {
    selected = Wire.read() % 3;
  }
  while (Wire.available()) Wire.read();  // ignore anything else
}

// Called when the BMC reads from us: send the selected register.
void onRequest() {
  Wire.write(regs[selected]);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(I2C_ADDRESS);  // join the bus as a target with this address
  Wire.onReceive(onReceive);
  Wire.onRequest(onRequest);
  randomSeed(analogRead(0));
}

void loop() {
  // Commands from the serial monitor.
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'h') hot = true;
    if (c == 'n') hot = false;
    if (c == 'f') fault = !fault;
  }

  // Make the readings move a little so you can see them change.
  int8_t temp = hot ? 75 : 24 + random(0, 4);   // °C
  uint8_t volt = 163 + random(0, 5);            // 3.26 .. 3.34 V

  uint8_t status = 0x01;                        // data ready
  if (temp > 50) status |= 0x02;                // alert
  if (fault)     status |= 0x80;                // fault

  noInterrupts();
  regs[0] = (uint8_t)temp;
  regs[1] = volt;
  regs[2] = status;
  interrupts();

  Serial.print("temp="); Serial.print(temp);
  Serial.print(" volt_raw="); Serial.print(volt);
  Serial.print(" status=0x"); Serial.println(status, HEX);
  delay(1000);
}
