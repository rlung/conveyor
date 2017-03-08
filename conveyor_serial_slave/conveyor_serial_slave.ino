/*
conveyor-serial-slave

Uses serial protocol to communicate with "master" arduino to obtain parameters. 
Data is transmitted in 3 bytes. The first byte signifies the beginning of the 
signal. The remaining two are the interval between steps and step amount.

*/


#include <Stepper.h>
#define STEPCODE 53

Stepper trackStepper(200, 8, 9, 10, 11);


void setup() {
  Serial.begin(9600);
}


void loop() {

  if (Serial.available() >= 3) {
    
    // Verify first byte is STEPCODE
    if (Serial.read() != STEPCODE) {
      return;
    }

    // Collect remaining two bytes (interval and step)
    byte interval = Serial.read();
    int steps     = Serial.read();
    int speed;
    
    // Define stepping parameters
    if (interval == 0) {
      // Values for moving backwards
      // Wire doesn't transmit negative values. Resetting conveyers must
      // be encoded differently.
      speed = 150;
      steps = -25;
    }
    else {
      // Speed is set as function of steps. Want to complete number of `steps` 
      // within alotted `interval`.
      //   Speed calculation:
      //   rot/min = steps / interval * 60000 ms/min / steps/rot
      // (Interval is typically 50 ms.)
      speed = steps * 300 / interval;

      // Relay confirmation data was received
      Serial.write(STEPCODE);
      Serial.write(steps);
    }

    // Move motor
    trackStepper.setSpeed(speed);
    trackStepper.step(steps);
  }

}
