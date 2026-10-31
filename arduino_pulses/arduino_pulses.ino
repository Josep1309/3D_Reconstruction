const int pinPulsoCamara = 9;    // PB1 en ATmega328P
const int pinPulsoProyector = 10; // PB2 en ATmega328P
// 20 Hz: un ciclo completo dura 50 ms y cada estado dura 25 ms.
const unsigned long semiPeriodo = 25000;

unsigned long tiempoPrevio = 0;
bool estadoPin = false;

void setup() {
  pinMode(pinPulsoCamara, OUTPUT);
  pinMode(pinPulsoProyector, OUTPUT);
}

void loop() {
  unsigned long tiempoActual = micros();

  if (tiempoActual - tiempoPrevio >= semiPeriodo) {
    tiempoPrevio += semiPeriodo; // Evita deriva acumulativa
    
    estadoPin = !estadoPin;
    if (estadoPin) {
      PORTB |= (1 << PB1) | (1 << PB2);  // Pines 9 y 10 en HIGH simultáneamente
    } else {
      PORTB &= ~((1 << PB1) | (1 << PB2)); // Pines 9 y 10 en LOW simultáneamente
    }
  }
}