# Система мониторинга безопасности для Friday Jarvis

Этот модуль добавляет в Friday Jarvis функциональность мониторинга безопасности с использованием веб-камеры. Система автоматически обнаруживает движение, записывает видео и отправляет уведомления по электронной почте или в Telegram.

## Возможности

- 📹 Обнаружение движения через веб-камеру
- 🎥 Автоматическая запись видео при обнаружении движения
- 📸 Создание скриншотов в момент обнаружения движения
- 📧 Отправка уведомлений по электронной почте с прикрепленным скриншотом
- 📱 Отправка уведомлений в Telegram с прикрепленным скриншотом
- ⚙️ Настраиваемые параметры чувствительности и длительности записи
- 🔄 Адаптация к изменениям освещения для минимизации ложных срабатываний

## Настройка

### 1. Настройка переменных окружения

Добавьте следующие строки в файл `.env`:

```
# Для отправки уведомлений по электронной почте
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your_app_password

# Для отправки уведомлений в Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 2. Установка зависимостей

Убедитесь, что все необходимые библиотеки установлены:

```bash
pip install opencv-python numpy imutils
```

## Использование

### Запуск мониторинга через Friday Jarvis

Система мониторинга безопасности интегрирована в Friday Jarvis как инструмент. Вы можете запустить её, попросив Jarvis:

```
Запусти мониторинг безопасности
```

Или с дополнительными параметрами:

```
Запусти мониторинг безопасности с чувствительностью 30 и уведомлениями в Telegram
```

### Остановка мониторинга

Чтобы остановить мониторинг безопасности, попросите Jarvis:

```
Останови мониторинг безопасности
```

## Настройка параметров

При запуске мониторинга безопасности вы можете настроить следующие параметры:

- **camera_id** - ID камеры (обычно 0 для встроенной веб-камеры)
- **sensitivity** - Чувствительность обнаружения движения (1-100, по умолчанию 20)
- **record_seconds** - Сколько секунд записывать после обнаружения движения (по умолчанию 10)
- **notify_method** - Метод уведомления ("email" или "telegram", по умолчанию "email")

## Как это работает

1. **Инициализация камеры**: Система получает доступ к веб-камере и начинает захват видео.
2. **Обнаружение движения**: Используется алгоритм вычитания фона для обнаружения изменений между кадрами.
3. **Запись видео**: При обнаружении движения система начинает запись видео в формате AVI.
4. **Отправка уведомлений**: Система делает скриншот и отправляет уведомление выбранным способом.
5. **Адаптация к освещению**: Каждые 30 секунд система обновляет эталонный кадр для адаптации к изменениям освещения.

## Хранение записей

Все видеозаписи и скриншоты сохраняются в директории `security_recordings` в формате:

- Видео: `motion_YYYYMMDD_HHMMSS.avi`
- Скриншоты: `motion_YYYYMMDD_HHMMSS.jpg`

## Устранение неполадок

### Камера не обнаруживается

1. Убедитесь, что камера подключена и работает
2. Попробуйте изменить параметр `camera_id` (0, 1, 2 и т.д.)
3. Проверьте, не используется ли камера другим приложением

### Не отправляются уведомления по электронной почте

1. Убедитесь, что в файле `.env` правильно указаны GMAIL_USER и GMAIL_APP_PASSWORD
2. Проверьте, что вы используете пароль приложения, а не обычный пароль от аккаунта
3. Убедитесь, что в вашем аккаунте Google разрешен доступ менее защищенным приложениям

### Не отправляются уведомления в Telegram

1. Убедитесь, что в файле `.env` правильно указаны TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID
2. Проверьте, что вы начали диалог с ботом в Telegram
3. Убедитесь, что бот имеет права на отправку сообщений в указанный чат

## Дополнительная информация

Для более подробной информации о работе системы мониторинга безопасности обратитесь к исходному коду в файле `security_monitor.py`.
