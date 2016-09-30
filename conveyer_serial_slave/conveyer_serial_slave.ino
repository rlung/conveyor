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


void loop() {

  if (Serial.available() >= 3) {
    
    if (Serial.read() != STEPCODE) {
      return;
    }

    byte interval = Serial.read();
    int steps     = Serial.read();
    int speed;
    
    // Values for moving backwards
    // Wire doesn't transmit negative values. Resetting conveyers must
    // be encoded differently (eg, 255, 255).
    if (interval == 0) {
      // Reset rail parameters
      speed = 180;
      steps = -25;
    }
    else {
      // Speed calculation based on 50-ms track interval and 200 steps/rotation.
      // Calculation: rot/min = steps(steps2take) / interval(50ms) * 60000 ms/min / steps/rot(200)
      // Max number of steps is constrained by byte max (255) and max allowed 
      // for step speed (assuming speed = steps * 6 thus 255/6 = 42).
      speed = steps * 300 / interval;

      // Relay confirmation data was received
      Serial.write(STEPCODE);
      Serial.write(steps);
    }

    trackStepper.setSpeed(speed);
    trackStepper.step(steps);
  }

}

/*
void loop() {

  if (Serial.available() >= 3) {
    if (Serial.parseInt() != STEPCODE) {
      return;
    }
    byte interval = Serial.parseInt();
    int steps     = Serial.parseInt();
    int speed;

    Serial.print("interval: ");
    Serial.print(interval);
    Serial.print(" | steps: ");
    Serial.println(steps);
    
    // Values for moving backwards
    // Wire doesn't transmit negative values. Resetting conveyers must
    // be encoded differently (eg, 255, 255).
    if (interval == 0) {
      Serial.println("Moving back.");
      speed = 180;
      steps = -25;
    }
    else {
      // Speed calculation based on 50-ms track interval and 200 steps/rotation.
      // Calculation: rot/min = steps(steps2take) / interval(50ms) * 60000 ms/min / steps/rot(200)
      // Max number of steps is constrained by byte max (255) and max allowed 
      // for step speed (assuming speed = steps * 6 thus 255/6 = 42).
      speed = steps * 300/interval;

      // Relay confirmation data was received
      Serial.write(STEPCODE);
      Serial.write(steps);
    }

    Serial.print("interval: ");
    Serial.print(interval);
    Serial.print(" | steps: ");
    Serial.print(steps);
    Serial.print(" | speed: ");
    Serial.println(speed);

    trackStepper.setSpeed(speed);
    trackStepper.step(steps);
  }

}


void loop() {

  if (Serial.available() >= 3) {
    if (Serial.read() != STEPCODE) {
      return;
    }
    byte interval = Serial.read();
    int steps     = Serial.read();
    int speed;
    
    // Values for moving backwards
    // Necessary bc negative values are not transmitted
    if (interval == 0) {
      speed = 180;
      steps = -25;
    }
    else {
      // Speed calculation based on 50-ms track interval and 200 steps/rotation.
      // Calculation: rot/min = steps(steps2take) / interval(50ms) * 60000 ms/min / steps/rot(200)
      // Max number of steps is constrained by byte max (255) and max allowed 
      // for step speed (assuming speed = steps * 6 thus 255/6 = 42).
      speed = steps * 300/interval;

      // Relay confirmation data was received
      Serial.write(STEPCODE);
      Serial.write(steps);
    }

    trackStepper.setSpeed(speed);
    trackStepper.step(steps);
  }

}
*/