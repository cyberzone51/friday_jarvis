import cv2
import numpy as np
import time
import datetime
import os
import threading
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

class SecurityMonitor:
    def __init__(self, 
                 camera_id=0, 
                 sensitivity=20, 
                 min_area=500, 
                 record_seconds=10,
                 notify_method="email",
                 save_dir="security_recordings"):
        """
        Инициализация монитора безопасности.
        
        Args:
            camera_id: ID камеры (обычно 0 для встроенной веб-камеры)
            sensitivity: Чувствительность обнаружения движения (1-100)
            min_area: Минимальная площадь для обнаружения движения
            record_seconds: Сколько секунд записывать после обнаружения движения
            notify_method: Метод уведомления ("email" или "telegram")
            save_dir: Директория для сохранения записей
        """
        self.camera_id = camera_id
        self.sensitivity = sensitivity
        self.min_area = min_area
        self.record_seconds = record_seconds
        self.notify_method = notify_method
        self.save_dir = save_dir
        
        # Создаем директорию для сохранения записей, если она не существует
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            
        self.is_running = False
        self.camera = None
        self.monitor_thread = None
        
        # Загрузка настроек из переменных окружения
        self.gmail_user = os.getenv("GMAIL_USER")
        self.gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
    def start(self):
        """Запуск мониторинга безопасности в отдельном потоке."""
        if self.is_running:
            logger.info("Мониторинг безопасности уже запущен")
            return "Мониторинг безопасности уже запущен"
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logger.info("Мониторинг безопасности запущен")
        return "Мониторинг безопасности запущен"
    
    def stop(self):
        """Остановка мониторинга безопасности."""
        if not self.is_running:
            logger.info("Мониторинг безопасности не запущен")
            return "Мониторинг безопасности не запущен"
        
        self.is_running = False
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        
        logger.info("Мониторинг безопасности остановлен")
        return "Мониторинг безопасности остановлен"
    
    def _monitor_loop(self):
        """Основной цикл мониторинга."""
        try:
            # Инициализация камеры
            self.camera = cv2.VideoCapture(self.camera_id)
            if not self.camera.isOpened():
                logger.error(f"Не удалось открыть камеру с ID {self.camera_id}")
                self.is_running = False
                return
            
            # Получение первого кадра для сравнения
            _, first_frame = self.camera.read()
            gray_first_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
            gray_first_frame = cv2.GaussianBlur(gray_first_frame, (21, 21), 0)
            
            # Настройки для записи видео
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            frame_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(self.camera.get(cv2.CAP_PROP_FPS))
            
            is_recording = False
            video_writer = None
            record_start_time = None
            
            while self.is_running:
                # Чтение кадра
                ret, frame = self.camera.read()
                if not ret:
                    logger.error("Ошибка при чтении кадра с камеры")
                    break
                
                # Преобразование кадра для обнаружения движения
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray_frame = cv2.GaussianBlur(gray_frame, (21, 21), 0)
                
                # Вычисление разницы между текущим и первым кадром
                frame_delta = cv2.absdiff(gray_first_frame, gray_frame)
                thresh = cv2.threshold(frame_delta, self.sensitivity, 255, cv2.THRESH_BINARY)[1]
                
                # Расширение порогового изображения для заполнения отверстий
                thresh = cv2.dilate(thresh, None, iterations=2)
                contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                motion_detected = False
                
                # Проверка контуров на наличие движения
                for contour in contours:
                    if cv2.contourArea(contour) < self.min_area:
                        continue
                    
                    motion_detected = True
                    (x, y, w, h) = cv2.boundingRect(contour)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # Если обнаружено движение и не идет запись, начинаем запись
                if motion_detected and not is_recording:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_path = os.path.join(self.save_dir, f"motion_{timestamp}.avi")
                    video_writer = cv2.VideoWriter(video_path, fourcc, fps, (frame_width, frame_height))
                    is_recording = True
                    record_start_time = time.time()
                    
                    # Сохраняем скриншот для уведомления
                    screenshot_path = os.path.join(self.save_dir, f"motion_{timestamp}.jpg")
                    cv2.imwrite(screenshot_path, frame)
                    
                    # Отправляем уведомление
                    self._send_notification(screenshot_path)
                    
                    logger.info(f"Обнаружено движение! Начата запись: {video_path}")
                
                # Если идет запись, записываем кадр
                if is_recording:
                    video_writer.write(frame)
                    
                    # Проверяем, не истекло ли время записи
                    if time.time() - record_start_time > self.record_seconds:
                        video_writer.release()
                        video_writer = None
                        is_recording = False
                        logger.info("Запись завершена")
                
                # Обновляем первый кадр каждые 30 секунд для адаптации к изменениям освещения
                if time.time() % 30 < 1:
                    gray_first_frame = gray_frame
                
                # Добавляем временную метку на кадр
                cv2.putText(frame, datetime.datetime.now().strftime("%A %d %B %Y %I:%M:%S%p"),
                            (10, frame_height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                
                # Отображаем кадр (в реальном приложении можно закомментировать)
                # cv2.imshow("Security Feed", frame)
                
                # Проверяем нажатие клавиши 'q' для выхода
                # if cv2.waitKey(1) & 0xFF == ord('q'):
                #     break
                
                # Небольшая задержка для снижения нагрузки на CPU
                time.sleep(0.01)
            
            # Освобождаем ресурсы
            if video_writer is not None:
                video_writer.release()
            
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга: {e}")
        finally:
            if self.camera is not None:
                self.camera.release()
            # cv2.destroyAllWindows()
            self.is_running = False
    
    def _send_notification(self, screenshot_path):
        """Отправка уведомления о обнаружении движения."""
        try:
            if self.notify_method == "email" and self.gmail_user and self.gmail_password:
                self._send_email_notification(screenshot_path)
            elif self.notify_method == "telegram" and self.telegram_bot_token and self.telegram_chat_id:
                self._send_telegram_notification(screenshot_path)
            else:
                logger.warning(f"Метод уведомления '{self.notify_method}' не настроен или не поддерживается")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")
    
    def _send_email_notification(self, screenshot_path):
        """Отправка уведомления по электронной почте."""
        try:
            # Gmail SMTP конфигурация
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            
            # Создание сообщения
            msg = MIMEMultipart()
            msg['From'] = self.gmail_user
            msg['To'] = self.gmail_user  # Отправляем на тот же адрес
            msg['Subject'] = "ТРЕВОГА! Обнаружено движение"
            
            # Текст сообщения
            body = f"Система безопасности обнаружила движение в {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}."
            msg.attach(MIMEText(body, 'plain'))
            
            # Прикрепляем скриншот
            with open(screenshot_path, 'rb') as f:
                img_data = f.read()
                image = MIMEImage(img_data, name=os.path.basename(screenshot_path))
                msg.attach(image)
            
            # Подключение к серверу SMTP
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(self.gmail_user, self.gmail_password)
            
            # Отправка сообщения
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Уведомление по электронной почте отправлено на {self.gmail_user}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления по электронной почте: {e}")
    
    def _send_telegram_notification(self, screenshot_path):
        """Отправка уведомления в Telegram."""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendPhoto"
            
            # Текст сообщения
            caption = f"🚨 ТРЕВОГА! Обнаружено движение в {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}."
            
            # Отправка запроса
            with open(screenshot_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': self.telegram_chat_id, 'caption': caption}
                response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                logger.info(f"Уведомление в Telegram отправлено в чат {self.telegram_chat_id}")
            else:
                logger.error(f"Ошибка при отправке уведомления в Telegram: {response.text}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")

# Функция для запуска мониторинга безопасности
def start_security_monitoring(camera_id=0, sensitivity=20, record_seconds=10, notify_method="email"):
    """
    Запускает мониторинг безопасности с указанными параметрами.
    
    Args:
        camera_id: ID камеры (обычно 0 для встроенной веб-камеры)
        sensitivity: Чувствительность обнаружения движения (1-100)
        record_seconds: Сколько секунд записывать после обнаружения движения
        notify_method: Метод уведомления ("email" или "telegram")
    
    Returns:
        str: Сообщение о результате запуска
    """
    monitor = SecurityMonitor(
        camera_id=camera_id,
        sensitivity=sensitivity,
        record_seconds=record_seconds,
        notify_method=notify_method
    )
    return monitor.start()

# Функция для остановки мониторинга безопасности
def stop_security_monitoring():
    """
    Останавливает мониторинг безопасности.
    
    Returns:
        str: Сообщение о результате остановки
    """
    # Поскольку монитор запускается в отдельном потоке, нам нужно иметь глобальную переменную
    # для хранения экземпляра монитора. В реальном приложении это можно реализовать лучше.
    global security_monitor_instance
    if 'security_monitor_instance' in globals() and security_monitor_instance is not None:
        result = security_monitor_instance.stop()
        security_monitor_instance = None
        return result
    else:
        return "Мониторинг безопасности не был запущен"

# Глобальная переменная для хранения экземпляра монитора
security_monitor_instance = None

if __name__ == "__main__":
    # Пример использования
    start_security_monitoring(sensitivity=30, notify_method="email")
    
    # Для тестирования можно добавить задержку и затем остановить мониторинг
    # import time
    # time.sleep(60)  # Мониторинг в течение 60 секунд
    # stop_security_monitoring()
