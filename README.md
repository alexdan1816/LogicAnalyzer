# STM32F411 8-Channel 1MHz Logic Analyzer

A high-performance, low-cost 8-channel logic analyzer firmware built on the **STM32F411 (Black Pill)** board. It utilizes a zero-CPU-overhead **Timer-DMA hardware automation architecture** to sample digital signals at 1 MHz and streams the captured data to PC software (such as PulseView) via USB CDC.

---

## 🚀 Key Features

* **8 Digital Channels:** Samples parallel inputs simultaneously across Port B (`PB0` - `PB7`).
* **True 1 MHz Sampling Rate:** Achieved using hardware timer triggers coupled with direct memory access.
* **Zero CPU Overhead During Acquisition:** Uses **TIM1 Update Event (`TIM1_UP`)** to trigger **DMA Peripheral-to-Memory** transfers directly from the `GPIOB->IDR` register to SRAM, completely bypassing the CPU during sampling.
* **Hardware Protection:** Incorporates level shifters/buffers to protect MCU pins and ensure signal integrity.
* **PC Software Integration:** Interfaces smoothly with PC software via UART/USB COM port.

---

## 🛠️ System Architecture & Data Flow

### 📊 Sơ đồ luồng hoạt động (Code Flowchart)

```text
[MCU Boot & Init]
    │
    ├─> HAL_Init() & SystemClock_Config()
    ├─> MX_GPIO_Init()      --> Cấu hình các chân GPIOB làm Input (PB0-PB7)
    ├─> MX_DMA_Init()       --> Cấu hình DMA2_Stream5 và ngắt
    ├─> MX_TIM1_Init()      --> Cấu hình Timer 1 (tạo trigger mẫu mỗi 1 us)
    ├─> MX_USART1_UART_Init() --> UART gửi dữ liệu mẫu thu được lên máy tính
    └─> MX_USART2_UART_Init() --> UART debug / thông báo trạng thái
    │
[Khởi động phiên đo đạc (User Code bên trong main)]
    │
    ├─> Đăng ký callback: hdma_tim1_up.XferCpltCallback = LA_TransferComplete_CallBack;
    ├─> Bắt đầu DMA ngắt:  HAL_DMA_Start_IT(..., &(GPIOB->IDR), sample_buffer, BUFFER_SIZE);
    ├─> Kích hoạt DMA từ Timer: __HAL_TIM_ENABLE_DMA(&htim1, TIM_DMA_UPDATE);
    ├─> Kích hoạt Timer 1: __HAL_TIM_ENABLE(&htim1);
    │
    ▼
[Vòng lặp vô hạn (while(1))]
    │
    ├─> Kiểm tra cờ `is_sampling_done`?
    │     │
    │     ├── (Chưa xong) ──> Tiếp tục vòng lặp chờ đợi...
    │     │
    │     └── (Đã xong: is_sampling_done == 1)
    │           │
    │           ├─> HAL_Delay(5000) (Chờ ổn định)
    │           ├─> Reset cờ: is_sampling_done = 0;
    │           ├─> Truyền dữ liệu qua UART1: HAL_UART_Transmit(&huart1, sample_buffer, BUFFER_SIZE, ...)
    │           ├─> HAL_Delay(5000)
    │           ├─> Khởi động lại phiên đo DMA mới (Cài lại DMA, bật lại Timer DMA, bật lại Timer 1)
    │           └─> Gửi ký tự thông báo qua UART2 (`test = 'A'`)
    │
    ▼
[Ngắt hoàn thành DMA (LA_TransferComplete_CallBack)]
    │  (Được gọi tự động khi DMA đã nạp đủ BUFFER_SIZE = 16384 mẫu)
    ├─> Dừng Timer 1: HAL_TIM_Base_Stop(&htim1);
    ├─> Tắt yêu cầu DMA của Timer: __HAL_TIM_DISABLE_DMA(&htim1, TIM_DMA_UPDATE);
    └─> Bật cờ báo hoàn thành: is_sampling_done = 1;
```

---

## 📌 Pinout Configuration

| STM32 Pin | Channel / Signal | Description |
| :--- | :--- | :--- |
| **PB0 - PB7** | CH0 - CH7 | Digital input channels |
| **GND** | Ground | Mandatory common ground reference with target device |
| **USART1 / USB** | Telemetry | UART/USB communication with host PC |

---

## ⚙️ Hardware & Software Requirements

* **Hardware:**
  * STM32F411 Development Board
  * Level Shifter IC
  * Logic level connections and common GND wire
* **Software Toolchain:**
  * STM32CubeMX / STM32CubeIDE / GCC toolchain
  * Terminal / PulseView on the host PC for data/waveform visualization

---

## 📝 Getting Started

1. Clone or download this repository.
2. Open the project configuration in **STM32CubeMX** to verify TIM1 and DMA requests.
3. Build and flash the firmware onto your STM32F411 board using STM32CubeIDE.
4. Connect your target signals to channels CH0-CH7 and plug into your computer.
5. Open your terminal or PC software to receive data streams!

---

## 📄 License
This project is open-source, released under the [MIT License](LICENSE).


