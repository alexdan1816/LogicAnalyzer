#include <Wire.h>
#include <HardwareSerial.h>

HardwareSerial myUart(0);
const int TX_PIN = 21;
const int RX_PIN = 20;

char c = 'A';
char msg[] = "Hello";

String test = "Hello";

const int SCL_PIN = 9;
const int SDA_PIN = 8;
void setup()
{
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);
  myUart.begin(115200, SERIAL_8N1, RX_PIN, TX_PIN);

  // Serial.println("Khởi tạo UART TX 21 thành công");
  // Serial1.begin(115200, SERIAL_8N1, 20, 21);

}

void loop()
{
  
  // // Gửi kí tự 'A' qua chân TX (GPIO 21)
  myUart.print("Hello");
  Wire.beginTransmission(0x3C); 

  // Bước 2: Đẩy dữ liệu vào bộ đệm (Buffer)
  Wire.write(0x00);        // Gửi một byte lệnh hoặc địa chỉ thanh ghi phụ
  Wire.write((const uint8_t*)msg, 5); // Gửi chuỗi "Hello" dài 5 byte qua I2C
  Wire.write(0xAF);        // Gửi một byte dữ liệu dạng HEX

  // Bước 3: Phát tín hiệu Stop và thực sự đẩy dữ liệu đi trên bus
  uint8_t status = Wire.endTransmission();
  // // In thông báo lên Serial Monitor để bạn dễ theo dõi
  // Serial1.println('A');
  
  // Chờ 3 giây rồi gửi tiếp
  delay(3000);
}