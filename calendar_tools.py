import os
import datetime
import logging
from typing import List, Optional
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Если изменить эти области, удалите файл token.pickle
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarAPI:
    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        """
        Инициализация API Google Calendar.
        
        Args:
            credentials_path: Путь к файлу credentials.json
            token_path: Путь к файлу token.pickle
        """
        self.credentials_path = credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        self.token_path = token_path or os.getenv("GOOGLE_TOKEN_PATH", "token.pickle")
        self.service = None
        
    def authenticate(self) -> bool:
        """
        Аутентификация в Google Calendar API.
        
        Returns:
            bool: True, если аутентификация успешна, иначе False
        """
        try:
            creds = None
            
            # Проверяем, существует ли файл с токеном
            if os.path.exists(self.token_path):
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
            
            # Если нет действительных учетных данных, запрашиваем их
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_path):
                        logger.error(f"Файл учетных данных не найден: {self.credentials_path}")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Сохраняем учетные данные для следующего запуска
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
            
            # Создаем сервис
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Аутентификация в Google Calendar API успешна")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при аутентификации в Google Calendar API: {e}")
            return False
    
    def create_event(self, 
                     summary: str, 
                     start_time: str, 
                     end_time: str, 
                     description: str = "", 
                     location: str = "",
                     reminders: List[int] = None) -> Optional[str]:
        """
        Создание события в календаре.
        
        Args:
            summary: Название события
            start_time: Время начала в формате 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD'
            end_time: Время окончания в формате 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD'
            description: Описание события
            location: Место проведения
            reminders: Список времени напоминаний в минутах до начала события
            
        Returns:
            str: ID созданного события или None в случае ошибки
        """
        if not self.service:
            if not self.authenticate():
                return None
        
        try:
            # Парсинг времени начала и окончания
            start_datetime = self._parse_datetime(start_time)
            end_datetime = self._parse_datetime(end_time)
            
            if not start_datetime or not end_datetime:
                logger.error("Неверный формат времени")
                return None
            
            # Определение, является ли событие целодневным
            is_all_day = len(start_time) <= 10 and len(end_time) <= 10
            
            # Создание события
            event = {
                'summary': summary,
                'location': location,
                'description': description,
            }
            
            # Настройка времени начала и окончания
            if is_all_day:
                event['start'] = {'date': start_datetime.strftime('%Y-%m-%d')}
                event['end'] = {'date': end_datetime.strftime('%Y-%m-%d')}
            else:
                event['start'] = {'dateTime': start_datetime.isoformat(), 'timeZone': 'Europe/Moscow'}
                event['end'] = {'dateTime': end_datetime.isoformat(), 'timeZone': 'Europe/Moscow'}
            
            # Настройка напоминаний
            if reminders:
                event['reminders'] = {
                    'useDefault': False,
                    'overrides': [{'method': 'popup', 'minutes': minutes} for minutes in reminders]
                }
            else:
                event['reminders'] = {'useDefault': True}
            
            # Добавление события в календарь
            event = self.service.events().insert(calendarId='primary', body=event).execute()
            logger.info(f"Событие создано: {event.get('htmlLink')}")
            
            return event.get('id')
            
        except Exception as e:
            logger.error(f"Ошибка при создании события: {e}")
            return None
    
    def get_upcoming_events(self, days: int = 7, max_results: int = 10) -> List[dict]:
        """
        Получение предстоящих событий из календаря.
        
        Args:
            days: Количество дней для поиска событий
            max_results: Максимальное количество событий для возврата
            
        Returns:
            List[dict]: Список предстоящих событий
        """
        if not self.service:
            if not self.authenticate():
                return []
        
        try:
            # Получение текущего времени и времени через указанное количество дней
            now = datetime.datetime.utcnow()
            end_time = now + datetime.timedelta(days=days)
            
            # Запрос событий
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                logger.info("Предстоящих событий не найдено")
                return []
            
            # Форматирование событий для удобного отображения
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                is_all_day = 'date' in event['start']
                
                if is_all_day:
                    start_dt = datetime.datetime.strptime(start, '%Y-%m-%d')
                    start_str = start_dt.strftime('%d.%m.%Y')
                else:
                    start_dt = datetime.datetime.fromisoformat(start)
                    start_str = start_dt.strftime('%d.%m.%Y %H:%M')
                
                formatted_events.append({
                    'id': event['id'],
                    'summary': event['summary'],
                    'start': start_str,
                    'description': event.get('description', ''),
                    'location': event.get('location', ''),
                    'is_all_day': is_all_day
                })
            
            logger.info(f"Найдено {len(formatted_events)} предстоящих событий")
            return formatted_events
            
        except Exception as e:
            logger.error(f"Ошибка при получении предстоящих событий: {e}")
            return []
    
    def delete_event(self, event_id: str) -> bool:
        """
        Удаление события из календаря.
        
        Args:
            event_id: ID события для удаления
            
        Returns:
            bool: True, если удаление успешно, иначе False
        """
        if not self.service:
            if not self.authenticate():
                return False
        
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            logger.info(f"Событие {event_id} удалено")
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении события {event_id}: {e}")
            return False
    
    def update_event(self, 
                     event_id: str, 
                     summary: Optional[str] = None, 
                     start_time: Optional[str] = None, 
                     end_time: Optional[str] = None, 
                     description: Optional[str] = None, 
                     location: Optional[str] = None) -> bool:
        """
        Обновление события в календаре.
        
        Args:
            event_id: ID события для обновления
            summary: Новое название события
            start_time: Новое время начала в формате 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD'
            end_time: Новое время окончания в формате 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD'
            description: Новое описание события
            location: Новое место проведения
            
        Returns:
            bool: True, если обновление успешно, иначе False
        """
        if not self.service:
            if not self.authenticate():
                return False
        
        try:
            # Получение текущего события
            event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
            
            # Обновление полей события
            if summary:
                event['summary'] = summary
            
            if description is not None:
                event['description'] = description
            
            if location is not None:
                event['location'] = location
            
            # Обновление времени начала и окончания
            if start_time:
                start_datetime = self._parse_datetime(start_time)
                if not start_datetime:
                    logger.error("Неверный формат времени начала")
                    return False
                
                is_all_day = len(start_time) <= 10
                if is_all_day:
                    event['start'] = {'date': start_datetime.strftime('%Y-%m-%d')}
                else:
                    event['start'] = {'dateTime': start_datetime.isoformat(), 'timeZone': 'Europe/Moscow'}
            
            if end_time:
                end_datetime = self._parse_datetime(end_time)
                if not end_datetime:
                    logger.error("Неверный формат времени окончания")
                    return False
                
                is_all_day = len(end_time) <= 10
                if is_all_day:
                    event['end'] = {'date': end_datetime.strftime('%Y-%m-%d')}
                else:
                    event['end'] = {'dateTime': end_datetime.isoformat(), 'timeZone': 'Europe/Moscow'}
            
            # Обновление события в календаре
            updated_event = self.service.events().update(
                calendarId='primary', eventId=event_id, body=event).execute()
            
            logger.info(f"Событие {event_id} обновлено")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении события {event_id}: {e}")
            return False
    
    def _parse_datetime(self, datetime_str: str) -> Optional[datetime.datetime]:
        """
        Парсинг строки даты/времени в объект datetime.
        
        Args:
            datetime_str: Строка даты/времени в формате 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD'
            
        Returns:
            datetime.datetime: Объект datetime или None в случае ошибки
        """
        try:
            if len(datetime_str) <= 10:  # Только дата
                return datetime.datetime.strptime(datetime_str, '%Y-%m-%d')
            else:  # Дата и время
                return datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        except ValueError:
            logger.error(f"Неверный формат даты/времени: {datetime_str}")
            return None

# Создание экземпляра API
calendar_api = GoogleCalendarAPI()

# Функции для использования в качестве инструментов

def create_calendar_event(summary: str, 
                         start_time: str, 
                         end_time: str, 
                         description: str = "", 
                         location: str = "",
                         reminders: List[int] = None) -> str:
    """
    Создание события в Google Calendar.
    
    Args:
        summary: Название события
        start_time: Время начала в формате 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD'
        end_time: Время окончания в формате 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD'
        description: Описание события
        location: Место проведения
        reminders: Список времени напоминаний в минутах до начала события
        
    Returns:
        str: Сообщение о результате создания события
    """
    event_id = calendar_api.create_event(
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        description=description,
        location=location,
        reminders=reminders
    )
    
    if event_id:
        return f"Событие '{summary}' успешно создано в календаре"
    else:
        return "Не удалось создать событие в календаре. Проверьте настройки аутентификации и формат данных."

def get_upcoming_events(days: int = 7) -> str:
    """
    Получение предстоящих событий из Google Calendar.
    
    Args:
        days: Количество дней для поиска событий
        
    Returns:
        str: Форматированный список предстоящих событий
    """
    events = calendar_api.get_upcoming_events(days=days)
    
    if not events:
        return f"В ближайшие {days} дней нет запланированных событий"
    
    result = f"Предстоящие события на ближайшие {days} дней:\n\n"
    
    for i, event in enumerate(events, 1):
        result += f"{i}. {event['summary']} - {event['start']}\n"
        if event['location']:
            result += f"   Место: {event['location']}\n"
        if event['description']:
            result += f"   Описание: {event['description']}\n"
        result += "\n"
    
    return result

def delete_calendar_event(event_id: str) -> str:
    """
    Удаление события из Google Calendar.
    
    Args:
        event_id: ID события для удаления
        
    Returns:
        str: Сообщение о результате удаления события
    """
    success = calendar_api.delete_event(event_id)
    
    if success:
        return f"Событие с ID {event_id} успешно удалено из календаря"
    else:
        return f"Не удалось удалить событие с ID {event_id}. Проверьте ID события и настройки аутентификации."

def update_calendar_event(event_id: str, 
                         summary: Optional[str] = None, 
                         start_time: Optional[str] = None, 
                         end_time: Optional[str] = None, 
                         description: Optional[str] = None, 
                         location: Optional[str] = None) -> str:
    """
    Обновление события в Google Calendar.
    
    Args:
        event_id: ID события для обновления
        summary: Новое название события
        start_time: Новое время начала в формате 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD'
        end_time: Новое время окончания в формате 'YYYY-MM-DD HH:MM' или 'YYYY-MM-DD'
        description: Новое описание события
        location: Новое место проведения
        
    Returns:
        str: Сообщение о результате обновления события
    """
    success = calendar_api.update_event(
        event_id=event_id,
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        description=description,
        location=location
    )
    
    if success:
        return f"Событие с ID {event_id} успешно обновлено"
    else:
        return f"Не удалось обновить событие с ID {event_id}. Проверьте ID события и настройки аутентификации."

if __name__ == "__main__":
    # Пример использования
    print(create_calendar_event(
        summary="Тестовое событие",
        start_time="2023-12-31 12:00",
        end_time="2023-12-31 13:00",
        description="Это тестовое событие",
        location="Онлайн",
        reminders=[10, 30]
    ))
    
    print(get_upcoming_events(days=30))
