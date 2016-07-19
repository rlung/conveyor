/*

Conveyer control
Randall Ung

Uses Wire (I2C) protocol to communicate with "master" arduino to obtain
parameters.

*/


#include <Wire.h>
#include <Stepper.h>

// Pins
const int step0 = 8;
const int step1 = 9;
const int step2 = 10;
const int step3 = 11;

const int spr = 200;  // steps per rotation of stepper
Stepper trackStepper(spr, step0, step1, step2, step3);

void setup() {
  Wire.begin(8);                // join i2c bus with address #8
  Wire.onReceive(stepIt);
  Serial.begin(9600);
}

void loop() {}

// function that executes whenever data is received from master
// this function is registered as an event, see setup()
void stepIt(int howMany) {
  byte speed = Wire.read();       // receive byte as an integer
  byte steps = Wire.read();

  Serial.print(speed);
  Serial.print(" ");
  Serial.println(steps);

//  trackStepper.setSpeed(speed);
//  trackStepper.step(steps);
}
