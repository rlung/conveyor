/*

Conveyer slave
Randall Ung

Uses serial protocol to communicate with "master" arduino to obtain parameters.

*/


#include <Stepper.h>
#define STEPCODE 53
Stepper trackStepper(200, 8, 9, 10, 11);

void setup() {
  Serial.begin(9600);
}
/*
void loop() {
  
  if (Serial.available() >= 3){
    if (Serial.read() != STEPCODE) {
      return;
    }
    byte speed = Serial.read();
    byte steps = Serial.read();

    // Check values for integrity
    if (speed == 0) return;
    if (speed < steps) return;
    
    // Values for moving backwards
    // Wire doesn't transmit negative values. Resetting conveyers must
    // be encoded differently (eg, 255, 255).
    if (speed == 255 && steps == 255) {
      trackStepper.setSpeed(180);
      trackStepper.step(-25);
    }
    else {
      trackStepper.setSpeed(speed);
      trackStepper.step(steps);
    }
  }
}*/


void loop() {

if (Serial.available() >= 3){
  if (Serial.read() != STEPCODE) {
    return;
  }
  byte interval = Serial.read();
  byte steps    = Serial.read();
  
  // Values for moving backwards
  // Wire doesn't transmit negative values. Resetting conveyers must
  // be encoded differently (eg, 255, 255).
  if (interval == 0) {
    int speed = 180;
    int steps = -25;
  }
  else {
    // Speed calculation based on 50-ms track interval and 200 steps/rotation.
    // Calculation: rot/min = steps(steps2take) / interval(50ms) * 60000 ms/min / steps/rot(200)
    // Max number of steps is constrained by byte max (255) and max allowed 
    // for step speed (assuming speed = steps * 6 thus 255/6 = 42).
    int speed = steps * 300/interval;

    // Relay confirmation data was received
    Serial.write((byte)STEPCODE);
    Serial.write(steps);
  }

  trackStepper.setSpeed(speed);
  trackStepper.step(steps);
}