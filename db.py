from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from bson import ObjectId
from gridfs import GridFS
from pymongo import MongoClient

from config import MONGODB_URL, MONGODB_NAME, BOT_TOKEN

MONGODB_URI = MONGODB_URL
DB_NAME = MONGODB_NAME
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)
client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
fs = GridFS(db)
dp.middleware.setup(LoggingMiddleware())

orders_collection = db["orders"]
person_collection = db["user"]
catalog_collection = db['catalog']
admins_collection = db['admins']
black_list_collection = db['black_list']
users_collection = db["users"]
contacts_collection = db["contacts"]
pickup_collection = db['address']


async def update_user(user_id, user_data):
    person_collection.replace_one({"user_id": user_id}, user_data)


async def get_product_quantity(product_id, catalog_id):
    catalog = await get_catalog_by_id(catalog_id)
    if catalog:
        products = catalog.get('products', [])
        for product in products:
            if product.get('_id') == product_id:
                quantity = product.get('quantity', 0)
                return int(quantity)

    return 0


async def get_catalog_by_id(catalog_id):
    try:
        catalog = catalog_collection.find_one({"_id": ObjectId(catalog_id)})
        if catalog:
            return catalog
        else:
            return None
    except Exception as e:
        print(f"Ошибка при получении каталога: {e}")
        return None


async def get_product_data(product_id, catalog_id):
    catalog = await get_catalog_by_id(catalog_id)
    if catalog:
        products = catalog.get("products", [])
        for product in products:
            if str(product.get("_id")) == str(product_id):
                return {
                    'product_name': product.get('product_name'),
                    'product_price': product.get('product_price'),
                    'quantity': product.get('quantity')
                }

    return None


async def get_product_details_url(product_name, catalog_name):
    catalog = await get_catalog_by_name(catalog_name)

    if catalog:
        products = catalog.get('products', [])
        for product in products:
            if product.get('product_name') == product_name:
                link = product.get('link', 'нет')
                return link

    return 'нет'


async def get_pickup_address():
    result = pickup_collection.find_one()
    return result


async def add_pickup_address(messenger_name):
    messenger = pickup_collection.insert_one({"pickup": messenger_name})


async def update_pickup_address(new_address):
    result = pickup_collection.update_one({}, {"$set": {"pickup": new_address}}, upsert=True)
    return result.modified_count > 0


async def get_messanger_by_name(messenger_name):
    messenger = contacts_collection.find_one({"name": messenger_name})
    return messenger


async def get_contacts_by_messenger(messenger_name: str):
    messenger = await get_messanger_by_name(messenger_name)
    return messenger.get('link', []) if messenger and 'link' in messenger else []


async def addmessanger(messenger_name):
    messenger_name = messenger_name
    result = contacts_collection.insert_one({"name": messenger_name})


async def add_users(user_id):
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        users_collection.insert_one({
            "user_id": user_id,
            "registered_at": datetime.utcnow()
        })


async def get_users_count():
    return users_collection.count_documents({})


async def get_stats_for_period(start_date, end_date):
    stats = users_collection.count_documents({
        "registered_at": {
            "$gte": start_date,
            "$lt": end_date
        }
    })

    return f"Новых пользователей: {stats}"


async def get_messanger_from_db():
    messanger = contacts_collection.find()
    result = [dict(i) for i in messanger]
    return result


async def remove_contact_from_db(contact_name):
    result = contacts_collection.delete_one({"name.name": contact_name})
    return result.deleted_count > 0


async def save_image(photos):
    image_ids = []
    print(image_ids, photos)
    for photo in photos:
        print(photo)
        if photo:
            try:
                file_id = photo.file_id
                file = await bot.download_file_by_id(file_id)
                image_id = fs.put(file)
                image_ids.append(image_id)
            except (ValueError, KeyError) as e:
                print(f"Ошибка при обработке фотографии: {photo}, {e}")
                continue
        else:
            print("Пустой список фотографий")
            continue
    return image_ids


async def remove_category_from_db(category_id):
    result = catalog_collection.delete_one({"_id": ObjectId(category_id)})
    return result.deleted_count > 0


async def get_photo_file_by_id(image_ids):
    if isinstance(image_ids, list):
        image_id = image_ids[0]
    else:
        image_id = image_ids

    image = fs.get(ObjectId(image_id))
    if image:
        with open("temp_image.jpg", "wb") as temp_file:
            temp_file.write(image.read())

        return "temp_image.jpg"
    return None


async def get_admin_info(user_id):
    admin = admins_collection.find_one({"user_id": user_id})
    return admin


async def get_blacklist_info(user_id):
    user = black_list_collection.find_one({"user_id": user_id})
    return user


async def get_products_in_category(category_id):
    catalog = await get_catalog_by_id(category_id)
    if catalog:
        return catalog.get('products', [])
    return []


async def update_catalog_name(catalog_id, new_name):
    try:
        catalog_id = ObjectId(catalog_id)  # Преобразуем строку в ObjectId
        update_query = {"_id": catalog_id}
        update_operation = {"$set": {"name": new_name}}

        result = catalog_collection.update_one(update_query, update_operation)
        if result.modified_count == 0:
            raise ValueError("Каталог не найден или название не было изменено")
    except Exception as e:
        raise e


async def remove_admin_from_db(user_id):
    admins_collection.delete_one({"user_id": user_id})


async def remove_user_from_black_list(user_id):
    black_list_collection.delete_one({"user_id": user_id})


async def save_order(user_id, delivery_type, total_price, user_cart, catalog_id, delivery_address):
    current_time = datetime.now()
    order_data = {
        'user_id': user_id,
        'delivery_type': delivery_type,
        'total_price': total_price,
        'order_time': current_time,
        'products': list(user_cart.values()),
        'catalog_id': catalog_id,
        'delivery_address': delivery_address
    }

    for product_id, product_data in user_cart.items():
        await decrease_product_quantity(product_id, product_data['quantity'], catalog_id)

    result = orders_collection.insert_one(order_data)
    order_id = result.inserted_id

    return order_id


async def decrease_product_quantity(product_id, quantity_to_decrease, catalog_id):
    catalog = await get_catalog_by_id(catalog_id)
    if catalog:
        products = catalog.get('products', [])
        for product in products:
            if product.get('_id') == product_id:
                current_quantity = product.get('quantity', 0)

                if current_quantity >= quantity_to_decrease:
                    product['quantity'] = current_quantity - quantity_to_decrease

                    await update_product_in_catalog(catalog_id, product_id, product)
                else:
                    raise ValueError("Недостаточно товаров на складе")
                break
    else:
        raise ValueError("Категория не найдена")


async def update_product_attribute(catalog_id, product_id, selected_attribute, new_data):
    try:
        catalog = await get_catalog_by_id(str(catalog_id))
        if not catalog:
            raise ValueError("Категория не найдена")

        products = catalog.get('products', [])
        product_index = None
        for i, product in enumerate(products):
            if product['_id'] == ObjectId(product_id):
                product_index = i
                break

        if product_index is None:
            raise ValueError("Товар не найден")

        if selected_attribute == 'product_price':
            products[product_index]['product_price'] = float(new_data)
        elif selected_attribute == 'name_description':
            products[product_index]['name_description'] = new_data
        elif selected_attribute == 'product_name':
            products[product_index]['product_name'] = new_data
        elif selected_attribute == 'quantity':
            products[product_index]['quantity'] = int(new_data)
        else:
            raise ValueError("Неизвестный атрибут товара.")

        update_query = {"_id": ObjectId(catalog_id)}
        update_operation = {"$set": {"products": products}}

        catalog_collection.update_one(update_query, update_operation)
    except Exception as e:
        print(f"Ошибка при обновлении информации о товаре: {e}")


async def update_product_in_catalog(catalog_id, product_id, update_data):
    try:
        update_query = {"_id": ObjectId(catalog_id), "products._id": ObjectId(product_id)}
        update_operation = {"$set": {f"products.$.{key}": value for key, value in update_data.items()}}

        result = catalog_collection.update_one(update_query, update_operation)

        if result.modified_count == 0:
            raise ValueError("Товар не найден")
    except Exception as e:
        print(f"Ошибка при обновлении информации о товаре: {e}")


async def remove_product_from_db_by_id(catalog_id, product_id):
    catalog = await get_catalog_by_id(catalog_id)
    if not catalog:
        return False

    products = catalog.get('products', [])
    new_products = [product for product in products if product.get('_id') != product_id]

    catalog['products'] = new_products

    result = catalog_collection.update_one({"_id": catalog["_id"]}, {"$set": {"products": new_products}})

    return result.modified_count > 0


async def get_daily_stats(date):
    start = datetime(date.year, date.month, date.day)
    end = start + timedelta(days=1)

    stats = users_collection.count_documents({
        "registered_at": {
            "$gte": start,
            "$lt": end
        }
    })

    return stats


async def get_admins_ids_from_db():
    admin_ids = []
    users = await get_users_from_db()
    for user in users:
        user_id = user['user_id']
        admin_info = await get_admin_info(user_id)
        if admin_info:
            admin_ids.append(user_id)
    return admin_ids


async def get_admins_from_db():
    admins = admins_collection.find({}, {"user_id": 1})
    admin_ids = [admin['user_id'] for admin in admins]

    admins_info = []

    for admin_id in admin_ids:
        admin_info = admins_collection.find_one({"user_id": admin_id})
        if admin_info:
            admin_name = admin_info.get("admin_name", "Нет имени")
        else:
            admin_name = "Нет имени"

        user_info = person_collection.find_one({"user_id": admin_id})
        if user_info:
            user_name = user_info.get("name", "Нет имени")
            user_number = user_info.get("number", "Нет номера")
        else:
            user_name = "Нет имени"
            user_number = "Нет номера"

        admins_info.append({
            "user_id": admin_id,
            "admin_name": admin_name,
            "user_name": user_name,
            "user_number": user_number,
        })

    return admins_info


async def get_user_to_black_list():
    users = black_list_collection.find({}, {"user_id": 1})
    user_ids = [user['user_id'] for user in users]

    users_info = []

    for user_id in user_ids:
        user_info = black_list_collection.find_one({"user_id": user_id})
        if not user_info:
            user_name = "Нет имени"
        else:
            user_name = user_info.get("admin_name", "Нет имени")

        person_info = person_collection.find_one({"user_id": user_id})
        if person_info:
            user_name = person_info.get("name", "Нет имени")
            user_number = person_info.get("number", "Нет номера")
        else:
            user_number = "Нет номера"

        new_user_info = {
            "user_id": user_id,
            "user_name": user_name,
            "user_number": user_number
        }

        users_info.append(new_user_info)

    return users_info


async def add_admin_to_db(user_id, admin_name, admin_number):
    existing_admin = admins_collection.find_one({"user_id": user_id})
    if existing_admin:
        return False
    admin_data = {
        'user_id': user_id,
        'admin_name': admin_name,
        'admin_number': admin_number
    }
    result = admins_collection.insert_one(admin_data)
    return result.inserted_id


async def add_user_to_black_list(user_id, user_name, user_number):
    existing_user = black_list_collection.find_one({"user_id": user_id})
    if existing_user:
        return False
    black_list_data = {
        'user_id': user_id,
        'admin_name': user_name,
        'admin_number': user_number
    }
    result = black_list_collection.insert_one(black_list_data)
    return result.inserted_id


async def update_user_name(user_id, new_name):
    user = person_collection.find_one({"user_id": user_id})
    if user:
        user['name'] = new_name
        person_collection.replace_one({"user_id": user_id}, user)
        return True
    else:
        return False


async def update_user_number(user_id, new_number):
    user = person_collection.find_one({"user_id": user_id})
    if user:
        user['number'] = new_number
        person_collection.replace_one({"user_id": user_id}, user)
        return True
    else:
        return False


async def get_order_history(user_id):
    orders = list(orders_collection.find({"user_id": user_id}))
    return orders


async def add_user(user_id, name=None, number=None, delivery_type=None):
    user = person_collection.find_one({"user_id": user_id})
    if user:
        user.name = name
        if number is not None:
            user.number = number
        if delivery_type is not None:
            user.delivery_type = delivery_type
        user.save()
    else:
        user_data = {"user_id": user_id, "name": name, "number": number}
        if delivery_type is not None:
            user_data["delivery_type"] = delivery_type
        person_collection.insert_one(user_data)


async def get_user(user_id):
    user = person_collection.find_one({"user_id": user_id})
    return user


async def add_category(catalog_name):
    catalog = await get_catalog_by_name(catalog_name)

    if not catalog:
        catalog = {
            'name': catalog_name,
            'products': []
        }
        result = catalog_collection.insert_one(catalog)
    return result.inserted_id


async def get_categories_from_db():
    categories = catalog_collection.find()
    result = [category for category in categories]
    return result


async def get_categories():
    categories = catalog_collection.find({}).to_list(length=None)
    return categories


async def get_products(category_name):
    category = catalog_collection.find_one({"name": category_name})
    if category:
        products = category.get("products", [])
    else:
        products = []
    return products


async def get_products_in_category_by_id(category_id):
    category = catalog_collection.find_one({"_id": category_id})
    if category:
        products = category.get("products", [])
    else:
        products = []
    return products


async def add_product_to_category(category_name, product_info):
    catalog = await get_catalog_by_name(category_name)

    if not catalog:
        await add_catalog(category_name)
        catalog = await get_catalog_by_name(category_name)

    if 'products' not in catalog:
        catalog['products'] = []

    catalog['products'].append(product_info)

    catalog_collection.update_one({"name": category_name}, {"$set": {"products": catalog['products']}})

    return True


async def get_product_by_name(product_name):
    catalogs = await get_categories_from_db()

    for catalog in catalogs:
        products = catalog.get("products")
        if products:
            for product in products:
                if product.get("product_name") == product_name:
                    return product

    return None


async def get_product_by_id(catalog_id, product_id):
    try:
        catalog = catalog_collection.find_one({"_id": catalog_id})
        if catalog and 'products' in catalog:
            products = catalog['products']
            for product in products:
                if str(product.get('_id')) == str(product_id):
                    return product
        return None
    except Exception as e:
        print(f"Ошибка при поиске товара по _id: {e}")
        return None


async def get_catalog_by_name(catalog_name):
    catalog = catalog_collection.find_one({"name": catalog_name})
    return catalog


async def add_catalog(catalog_name):
    catalog_collection.insert_one({"name": catalog_name, "products": []})


async def get_users_from_db():
    users = person_collection.find({})
    return users


async def get_user_cart(user_id):
    user = await get_user(user_id)
    return user.get('cart', [])


async def add_to_cart(user_id, product_name):
    user = await get_user(user_id)
    cart = user.get('cart', [])

    for item in cart:
        if item['product_name'] == product_name:
            item['quantity'] += 1
            break
    else:
        cart.append({'product_name': product_name, 'quantity': 1})

    user['cart'] = cart
    await update_user_cart(user_id, cart)


async def remove_from_cart(user_id, product_name):
    user = await get_user(user_id)
    cart = user.get('cart', [])

    for item in cart:
        if item['product_name'] == product_name:
            item['quantity'] -= 1
            if item['quantity'] == 0:
                cart.remove(item)
            break

    user['cart'] = cart
    await update_user_cart(user_id, cart)


async def update_user_cart(user_id, cart):
    user = await get_user(user_id)
    user['cart'] = cart
    await update_user(user_id, user)


async def get_user_info(user_id):
    user = await get_user(user_id)
    if user:
        name = user.get('name', 'Нет имени')
        number = user.get('number', 'Нет номера')
        delivery_type = user.get('delivery_type', 'Не указан')
        return f"Имя: {name}\nНомер телефона: {number}\nТип доставки: {delivery_type}"
    else:
        return "Пользователь не найден"


async def get_user_orders(user_id):
    orders = await get_order_history(user_id)
    if orders:
        orders_info = ""
        for order in orders:
            order_time = order.get('order_time', 'Нет данных')
            total_price = order.get('total_price', 'Нет данных')
            orders_info += f"Дата заказа: {order_time}, Сумма заказа: {total_price}\n"
        return orders_info
    else:
        return "У пользователя нет заказов"
