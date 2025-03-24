import requests
import json
import os
from datetime import datetime
from tqdm import tqdm
from urllib.parse import urlparse


class VK:
    def __init__(self, vk_token, user_id):
        self.token = vk_token
        self.user_id = user_id
        self.api_url = 'https://api.vk.com/method/'

    def get_photos(self, album_id='profile', count=5):
        """Получение фотографий с профиля VK"""
        params = {
            'owner_id': self.user_id,
            'album_id': album_id,
            'extended': 1,
            'photo_sizes': 1,
            'count': count,
            'access_token': self.token,
            'v': '5.131'
        }

        try:
            response = requests.get(f'{self.api_url}photos.get', params=params)
            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                raise Exception(f"VK API error: {data['error']['error_msg']}")

            return data['response']['items']
        except Exception as e:
            print(f"Ошибка при получении фотографий: {e}")
            return None

    def _get_max_size_photo(self, photo):
        """Получение фото максимального размера (приватный метод)"""
        sizes = photo['sizes']
        max_size = max(sizes, key=lambda x: x['height'] * x['width'])
        return max_size

    def __process_photo_data(self, photo):
        """Обработка данных фото (приватный метод)"""
        max_size = self._get_max_size_photo(photo)
        likes = photo['likes']['count']
        date = datetime.fromtimestamp(photo['date']).strftime('%Y-%m-%d')

        # Формирование имени файла
        file_name = f"{likes}.jpg"
        if any(f['file_name'] == file_name for f in self._processed_photos):
            file_name = f"{likes}_{date}.jpg"

        return {
            'file_name': file_name,
            'size': max_size['type'],
            'url': max_size['url']
        }


class YandexDisk:
    def __init__(self, yandex_token):
        self.token = yandex_token
        self.headers = {
            'Authorization': f'OAuth {self.token}'
        }
        self.api_url = 'https://cloud-api.yandex.net/v1/disk/'

    def create_folder(self, folder_name):
        """Создание папки на Яндекс.Диске"""
        params = {'path': folder_name}
        response = requests.put(f'{self.api_url}resources',
                                headers=self.headers,
                                params=params)

        if response.status_code == 409:
            print(f"Папка '{folder_name}' уже существует")
        elif response.status_code == 201:
            print(f"Папка '{folder_name}' успешно создана")
        else:
            print(f"Ошибка при создании папки: {response.json()}")

    def upload_photo(self, url, file_name, folder_name):
        """Загрузка фото на Яндекс.Диск"""
        params = {
            'url': url,
            'path': f'{folder_name}/{file_name}',
            'disable_redirects': True
        }

        response = requests.post(f'{self.api_url}resources/upload',
                                 headers=self.headers,
                                 params=params)

        if response.status_code == 202:
            print(f"Фото {file_name} поставлено в очередь на загрузку")
            return True
        else:
            print(f"Ошибка при загрузке фото {file_name}: {response.json()}")
            return False


def main():
    # Ввод данных пользователем
    vk_user_id = input("Введите ID пользователя VK: ")
    vk_token = input("Введите токен VK: ")
    yandex_token = input("Введите токен Яндекс.Диска: ")

    # Создание экземпляров классов
    vk = VK(vk_token, vk_user_id)
    yandex = YandexDisk(yandex_token)

    # Получение фотографий из VK
    photos = vk.get_photos(count=5)
    if not photos:
        return

    # Обработка фотографий
    vk._processed_photos = []
    for photo in tqdm(photos, desc="Обработка фотографий"):
        processed = vk._VK__process_photo_data(photo)
        vk._processed_photos.append(processed)

    # Создание папки на Яндекс.Диске
    folder_name = f"VK_Backup_{vk_user_id}"
    yandex.create_folder(folder_name)

    # Загрузка фотографий на Яндекс.Диск
    for photo in tqdm(vk._processed_photos, desc="Загрузка на Яндекс.Диск"):
        yandex.upload_photo(photo['url'], photo['file_name'], folder_name)

    # Сохранение информации в JSON-файл
    with open('photos_info.json', 'w') as f:
        json.dump([{'file_name': p['file_name'], 'size': p['size']}
                   for p in vk._processed_photos], f, indent=4)

    print("Резервное копирование завершено!")
    print(f"Информация о фотографиях сохранена в photos_info.json")


if __name__ == '__main__':
    main()