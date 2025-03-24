import requests
import json
from datetime import datetime
from tqdm import tqdm
import time
import os


class VK:
    def __init__(self, vk_token, user_id):
        self.token = vk_token
        self.api_url = 'https://api.vk.com/method/'
        self.user_id = self._resolve_identifier(user_id)
        if not self.user_id:
            raise ValueError("Не удалось определить ID пользователя/группы")

    def _resolve_identifier(self, identifier):
        """Определяет ID по различным форматам ввода"""
        identifier = str(identifier).strip()

        if identifier.lstrip('-').isdigit():
            return int(identifier)

        for prefix in ['https://vk.com/', 'vk.com/', '@']:
            if identifier.startswith(prefix):
                identifier = identifier[len(prefix):]

        user_params = {
            'user_ids': identifier,
            'access_token': self.token,
            'v': '5.131'
        }

        try:
            response = requests.get(f'{self.api_url}users.get', params=user_params)
            data = response.json()

            if 'response' in data and data['response']:
                return data['response'][0]['id']

            group_id = identifier.replace('public', '').replace('club', '')
            group_params = {
                'group_id': group_id,
                'access_token': self.token,
                'v': '5.131'
            }
            response = requests.get(f'{self.api_url}groups.getById', params=group_params)
            data = response.json()

            if 'response' in data and data['response']:
                return -data['response'][0]['id']

        except Exception as e:
            print(f"Ошибка при определении ID: {e}")

        return None

    def get_photos_sorted_by_date(self, album_id='profile', count=5):
        """Получает фотографии из указанного альбома"""
        params = {
            'owner_id': self.user_id,
            'album_id': album_id,
            'extended': 1,
            'photo_sizes': 1,
            'count': 200,
            'access_token': self.token,
            'v': '5.131'
        }

        try:
            response = requests.get(f'{self.api_url}photos.get', params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                error_msg = data['error'].get('error_msg', 'Unknown VK API error')
                raise Exception(f"VK API error: {error_msg}")

            photos = data.get('response', {}).get('items', [])

            current_time = time.time()
            photos.sort(key=lambda x: abs(x['date'] - current_time))

            closest_photos = photos[:count]
            closest_photos.sort(key=lambda x: x['date'])

            return closest_photos

        except requests.exceptions.RequestException as e:
            print(f"Ошибка сети: {e}")
        except Exception as e:
            print(f"Ошибка при получении фотографий: {e}")

        return None

    def _process_photo(self, photo):
        """Обработка данных одной фотографии"""
        max_size = max(photo['sizes'], key=lambda x: x['height'] * x['width'])
        date = datetime.fromtimestamp(photo['date']).strftime('%d-%m-%Y')
        likes = photo['likes']['count']

        return {
            'file_name': f"{date}_{likes}.jpg",
            'size': max_size['type'],
            'url': max_size['url'],
            'date': photo['date'],
            'likes': likes,
            'date_str': date
        }


class YandexDisk:
    def __init__(self, yandex_token):
        self.token = yandex_token
        self.headers = {'Authorization': f'OAuth {self.token}'}
        self.api_url = 'https://cloud-api.yandex.net/v1/disk/'

    def create_folder(self, folder_name):
        """Создание папки с проверкой существования"""
        params = {'path': folder_name}
        try:
            response = requests.put(f'{self.api_url}resources',
                                    headers=self.headers,
                                    params=params,
                                    timeout=10)
            if response.status_code not in [201, 409]:
                print(f"Ошибка при создании папки: {response.json()}")
        except Exception as e:
            print(f"Ошибка сети при создании папки: {e}")

    def upload_photo(self, url, file_name, folder_name):
        """Загрузка фото с обработкой ошибок"""
        params = {
            'url': url,
            'path': f'{folder_name}/{file_name}',
            'disable_redirects': True
        }

        try:
            response = requests.post(f'{self.api_url}resources/upload',
                                     headers=self.headers,
                                     params=params,
                                     timeout=15)

            if response.status_code == 202:
                return True
            else:
                error = response.json().get('message', 'Unknown error')
                print(f"Ошибка при загрузке {file_name}: {error}")
        except Exception as e:
            print(f"Сетевая ошибка при загрузке {file_name}: {e}")

        return False


def load_tokens():
    """Загружает токены из файла tokens.json"""
    try:
        with open('tokens.json', 'r') as f:
            tokens = json.load(f)
            return tokens.get('vk_token'), tokens.get('yandex_token')
    except FileNotFoundError:
        print("Файл tokens.json не найден")
    except json.JSONDecodeError:
        print("Ошибка чтения tokens.json")
    return None, None


def select_album():
    """Выбор альбома из предопределенного списка"""
    albums = [
        {'id': 'profile', 'title': 'Фотографии профиля'},
        {'id': 'wall', 'title': 'Фотографии со стены'},
        {'id': 'saved', 'title': 'Сохраненные фотографии'}
    ]

    print("\nДоступные альбомы:")
    for i, album in enumerate(albums, 1):
        print(f"{i}. {album['title']}")

    while True:
        try:
            choice = int(input("\nВыберите номер альбома (1-3): "))
            if 1 <= choice <= 3:
                return albums[choice - 1]['id'], albums[choice - 1]['title']
            print("Некорректный номер, выберите от 1 до 3")
        except ValueError:
            print("Введите число от 1 до 3")


def main():
    print("VK Photo Backup Tool")
    print("--------------------\n")

    # Загрузка токенов из файла
    vk_token, yandex_token = load_tokens()
    if not vk_token or not yandex_token:
        print("Не удалось загрузить токены. Убедитесь, что файл tokens.json существует и содержит:")
        print('{"vk_token": "ваш_токен_vk", "yandex_token": "ваш_токен_яндекс"}')
        return

    try:
        vk_identifier = input("Введите ID пользователя/группы VK: ").strip()

        vk = VK(vk_token, vk_identifier)
        yandex = YandexDisk(yandex_token)

        # Выбираем альбом
        album_id, album_title = select_album()

        print(f"\nПолучаем фотографии из альбома '{album_title}'...")
        photos = vk.get_photos_sorted_by_date(album_id=album_id, count=5)
        if not photos:
            raise Exception("Не удалось получить фотографии. Возможно, альбом пуст или недоступен.")

        folder_name = f"VK_{album_title}_{abs(vk.user_id)}"[:50]
        print(f"\nСоздаем папку '{folder_name}' на Яндекс.Диске...")
        yandex.create_folder(folder_name)

        print("\nЗагружаем фотографии в хронологическом порядке...")
        results = []
        for photo in tqdm(photos, desc="Загрузка"):
            processed = vk._process_photo(photo)
            if yandex.upload_photo(processed['url'], processed['file_name'], folder_name):
                results.append({
                    'file_name': processed['file_name'],
                    'size': processed['size'],
                    'date': processed['date_str'],
                    'likes': processed['likes'],
                    'album': album_title,
                    'upload_order': len(results) + 1
                })

        # Сохраняем отчет
        report_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_name, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print("\nПорядок загрузки фотографий:")
        for i, photo in enumerate(results, 1):
            print(f"{i}. {photo['file_name']} (загружена {i}-й)")

        print(f"\nГотово! Загружено {len(results)} фотографий из альбома '{album_title}'.")
        print(f"Отчет сохранен в файл {report_name}")

    except Exception as e:
        print(f"\nОшибка: {e}")
    finally:
        input("\nНажмите Enter для выхода...")


if __name__ == '__main__':
    # Создаем файл tokens.json если его нет
    if not os.path.exists('tokens.json'):
        with open('tokens.json', 'w') as f:
            json.dump({
                "vk_token": "ваш_токен_vk",
                "yandex_token": "ваш_токен_яндекс"
            }, f, indent=2)
        print("Создан файл tokens.json. Заполните его своими токенами.")
    else:
        main()