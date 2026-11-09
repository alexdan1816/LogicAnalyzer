# STM32F411 8-Channel 1MHz Logic Analyzer

A high-performance, low-cost 8-channel logic analyzer firmware built on the **STM32F411 (Black Pill)** board. It utilizes a zero-CPU-overhead **Timer-DMA hardware automation architecture** to sample digital signals at 1 MHz and streams the captured data to PC software (such as PulseView) via USB CDC.

---

## 🚀 Key Features

* **8 Digital Channels:** Samples parallel inputs simultaneously across Port A (`PA0` - `PA7`).
* **True 1 MHz Sampling Rate:** Achieved using hardware timer triggers coupled with direct memory access.
* **Zero CPU Overhead During Acquisition:** Uses **TIM1 Update Event (`TIM1_UP`)** to trigger **DMA Peripheral-to-Memory** transfers directly from the `GPIOA->IDR` register to SRAM, completely bypassing the CPU during sampling.
* **Hardware Protection:** Incorporates **SN74LVC8T245** level shifters/buffers to protect MCU pins and ensure signal integrity.
* **PC Software Integration:** Interfaces smoothly with **PulseView (sigrok)** via USB Virtual COM Port (CDC).

---

## 🛠️ System Architecture & Data Flow

1. **Time Base:** `TIM1` configured with `PSC = 0` and `ARR = 99` (driven by system clock tree) generates a precise sampling tick.
2. **Data Acquisition:** Each timer overflow triggers a hardware DMA request (`TIM1_UP`), which instantly reads `GPIOA->IDR` and writes the byte into an SRAM buffer.
3. **Transfer Complete:** Once the buffer is full, a DMA interrupt fires, stops the timer, and flags the CPU to package and transmit the raw data over UART/USB CDC to the host computer.

---

## 📌 Pinout Configuration

| STM32 Pin | Channel / Signal | Description |
| :--- | :--- | :--- |
| **PA0 - PA7** | CH0 - CH7 | Digital input channels (buffered via SN74LVC8T245) |
| **GND** | Ground | Mandatory common ground reference with target device |
| **USART1 / USB** | Telemetry | UART/USB communication with host PC |

---

## ⚙️ Hardware & Software Requirements

* **Hardware:**
  * STM32F411 Development Board
  * SN74LVC8T245 Level Shifter IC
  * Logic level connections and common GND wire
* **Software Toolchain:**
  * STM32CubeMX / STM32CubeIDE / GCC toolchain
  * PulseView (sigrok suite) on the host PC for waveform visualization

---

## 📝 Getting Started

1. Clone or download this repository.
2. Open the project configuration in **STM32CubeMX** to verify TIM1 (`PSC=0`, `ARR=99`, DMA Request on `TIM1_UP`).
3. Build and flash the firmware onto your STM32F411 board using STM32CubeIDE.
4. Connect your target signals to channels CH0-CH7 and plug into your computer.
5. Open **PulseView**, select the appropriate device/COM port, set the sample rate, and hit **Run**!

---

## 📄 License
This project is open-source, released under the [MIT License](LICENSE).

