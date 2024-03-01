import os
import re
import subprocess
from datetime import datetime, timedelta
from PIL import Image
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputFile
from aiogram.utils.exceptions import ChatNotFound, MessageToEditNotFound
from bson import ObjectId
from config import admin_user_id, GROUP_CHAT_ID
from db import add_category, get_users_from_db, bot, get_categories_from_db, \
    add_product_to_category, \
    get_admins_from_db, dp, \
    remove_admin_from_db, get_admin_info, get_admins_ids_from_db, save_image, remove_category_from_db, \
    get_products_in_category, add_admin_to_db, get_user, \
    add_user, update_user_number, update_user_name, \
    get_photo_file_by_id, remove_product_from_db, get_products, save_order, get_order_history, \
    add_user_to_black_list, get_user_to_black_list, remove_user_from_black_list, get_blacklist_info, get_daily_stats, \
    add_users, get_stats_for_period, get_messanger_from_db, addmessanger, remove_contact_from_db, \
    add_pickup_address, get_pickup_address, \
    update_pickup_address, get_product_quantity, get_product_by_name, get_catalog_by_name, update_product_in_catalog, \
    get_user_info, get_user_orders
from states import ProductForm, NewCategory, UserForm, AddPerson, UpdateUserData, DeleteProduct, SetDeliveryState, \
    Broadcast, AddNewPerson, AddContactState, PickupAddressState, UpdateAddressState, \
    DeliveryState, EditProduct, UserPage

user_carts = {}
catalog_name_data = {}
order_time = datetime(2023, 11, 14, 2, 43, 35, 493799)
formatted_time = order_time.strftime("%Y-%m-%d %H:%M:%S")


async def get_catalogs_keyboard():
    catalogs = await get_categories_from_db()
    keyboard = InlineKeyboardMarkup()

    for catalog in catalogs:
        catalog_name = catalog.get('name', 'Нет имени')
        if isinstance(catalog_name, str):
            catalog_button_text = f"{catalog_name}"
            button = InlineKeyboardButton(catalog_button_text, callback_data=f"showproduct_{catalog_name}")
            keyboard.add(button)
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="назад"))
    return keyboard


menu_keyboard = InlineKeyboardMarkup(row_width=1)
menu_keyboard.add(
    InlineKeyboardButton(text="🗃️ Каталог", callback_data="show_catalog"),
    InlineKeyboardButton(text="🛒 Корзина", callback_data="show_cart"),
    InlineKeyboardButton(text="📖 Заказы", callback_data="show_orders"),
    InlineKeyboardButton(text="💼 Профиль", callback_data="show_profile"),
    InlineKeyboardButton(text="❗ FAQ", callback_data="show_help")
)


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.finish()
    await add_users(user_id)
    await bot.send_message(message.chat.id, "Ознакомьтесь с каталогом нашего магазина⤵",
                           reply_markup=menu_keyboard)


@dp.callback_query_handler(lambda c: c.data == "назад".lower())
async def go_to_main_menu(callback: types.CallbackQuery):
    user_id = callback.message.chat.id
    await bot.edit_message_text("Вы вернулись в главное меню.", user_id, callback.message.message_id,
                                reply_markup=menu_keyboard)


@dp.callback_query_handler(text="show_contacts")
async def show_contacts(callback_query: CallbackQuery):
    messengers = await get_messanger_from_db()
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Назад", callback_data="назад"))
    text = 'Контакты'
    if messengers:
        for messenger in messengers:
            name = messenger.get('name')
            text += f"\n{str(name.get('name')).capitalize()}: {str(name.get('link'))}"

        await bot.edit_message_text(
            text,
            callback_query.from_user.id,
            callback_query.message.message_id,
            reply_markup=keyboard
        )
    else:

        await bot.edit_message_text(
            'Контактов не оставили ☹',
            callback_query.from_user.id,
            callback_query.message.message_id,
            reply_markup=keyboard
        )


@dp.callback_query_handler(text="show_help")
async def show_help(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text="✉ Контакты", callback_data="show_contacts"), )
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data="назад"))
    chat_id = callback.message.chat.id
    text = "Для работы с ботом вам доступны следующие команды:\n\n"
    text += "🗃️ Каталог - просмотреть каталог товаров и добавить их в корзину\n"
    text += "🛒 Корзина - посмотреть выбранные товары и оформить заказ\n"
    text += "📖 Заказы - посмотреть ваши прошлые заказы\n"
    text += "💼 Профиль - изменить контактные данные\n"
    text += "✉ Контакты - связь с администрацией\n"
    await bot.edit_message_text(text, chat_id, callback.message.message_id, reply_markup=keyboard)


@dp.callback_query_handler(text="show_catalog")
async def menu_catalogs(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    keyboard = await get_catalogs_keyboard()
    if callback.message.text:
        await bot.edit_message_text("Выберите каталог:", user_id, callback.message.message_id, reply_markup=keyboard)
    else:
        await bot.send_message(user_id, "Выберите каталог:", reply_markup=keyboard)


def resize_image(image_path, width, height):
    image = Image.open(image_path)
    resized_image = image.resize((width, height), Image.LANCZOS)
    temp_image_path = "temp_image.jpg"
    resized_image.save(temp_image_path)

    return temp_image_path


@dp.callback_query_handler(lambda c: c.data.startswith('showproduct_'))
async def show_category_products(callback_query: types.CallbackQuery):
    catalog_name = callback_query.data.split('_')[1]
    catalog_name_data[callback_query.from_user.id] = catalog_name
    products = await get_products(catalog_name)

    if products:
        for product in products:
            if product:
                product_name = product['product_name']
                image_path = await get_photo_file_by_id(product['image_id'])
                name_description = product.get('name_description', ' ')
                quantity = await get_product_quantity(product_name, catalog_name)
                cart_button = types.InlineKeyboardButton(
                    text="В корзину",
                    callback_data=f"addtocart_{product['product_name']}_{catalog_name}_{product['product_price']}".replace(
                        " ", "")
                )
                keyboard = InlineKeyboardMarkup(row_width=2)
                keyboard.add(cart_button)
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='show_catalog'))
                photo_caption = f"{product['product_name']}, {name_description}\n" \
                                f"Цена: {product['product_price']} сом\n" \
                                f"Количество: {product['quantity']} штук"
                # Нужно выбрать размер для картинок у товаров, они будут все на 1 размер
                resized_image_path = resize_image(image_path, 400, 300)

                with open(resized_image_path, 'rb') as photo_file:
                    await bot.send_photo(
                        chat_id=callback_query.from_user.id,
                        photo=InputFile(photo_file),
                        caption=photo_caption,
                        reply_markup=keyboard
                    )

                os.remove(resized_image_path)
            else:
                await callback_query.answer("Товар не найден.", show_alert=True)
    else:
        await callback_query.answer("Каталог пуст", show_alert=True)


async def show_cart_contents(user_id):
    cart_contents = user_carts.get(user_id, {})
    if not cart_contents:
        await bot.send_message(user_id, "Ваша корзина пуста.")
    else:
        for product_name, product_data in cart_contents.items():
            quantity = product_data['quantity']
            price = product_data['price']
            total_price = quantity * price
            await bot.send_message(user_id, f"Товар: {product_name}\nКоличество: {quantity}\nЦена: {total_price} сом")


@dp.callback_query_handler(lambda c: c.data.startswith('addtocart_'))
async def add_to_cart(callback_query: types.CallbackQuery):
    product_data = callback_query.data.split('_')
    product_price = float(product_data[3])
    catalog_name = product_data[2]
    product_name = product_data[1]
    user_id = callback_query.from_user.id
    user_cart = user_carts.setdefault(user_id, {})
    available_quantity = await get_product_quantity(product_name, catalog_name)
    if available_quantity > 0:
        if product_name not in user_cart or user_cart[product_name]['quantity'] < available_quantity:
            if product_name not in user_cart:
                user_cart[product_name] = {'quantity': 1, 'price': product_price}
            else:
                user_cart[product_name]['quantity'] += 1

            await update_product_buttons(callback_query, product_name, catalog_name, user_id, product_price)
        else:
            await bot.answer_callback_query(callback_query.id, text="Достигнуто максимальное количество товара",
                                            show_alert=True)
    else:
        await bot.answer_callback_query(callback_query.id, text="Товара нет в наличии", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith('addname_'))
async def add_product_to_cart(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    product_data = callback_query.data.split('_')
    product_price = float(product_data[2])
    product_name = product_data[1]
    catalog_name = product_data[3]
    user_cart = user_carts.setdefault(user_id, {})

    if user_cart and product_name in user_cart:
        user_cart[product_name]['quantity'] += 1
    else:
        user_cart[product_name] = {'quantity': 1, 'price': product_price}

    await update_product_buttons(callback_query, product_name, catalog_name, user_id, product_price)


@dp.callback_query_handler(lambda c: c.data.startswith('remove_'))
async def remove_product(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    product_data = callback_query.data.split('_')
    product_price = float(product_data[2])
    product_name = product_data[1]
    catalog_name = product_data[3]
    user_cart = user_carts.setdefault(user_id, {})

    if product_name in user_cart:

        if user_cart[product_name]['quantity'] > 0:
            user_cart[product_name]['quantity'] -= 1

            if user_cart[product_name]['quantity'] == 0:
                del user_cart[product_name]

        await update_product_buttons(callback_query, product_name, catalog_name, user_id, product_price)


async def generate_cart_buttons(product_name, catalog_name, user_id, price, count):
    available_quantity = await get_product_quantity(product_name, catalog_name)
    buttons = []

    if count < available_quantity:
        add_button = types.InlineKeyboardButton("Добавить",
                                                callback_data=f"addname_{product_name}_{price}_{catalog_name}")
        buttons.append(add_button)

    remove_button = types.InlineKeyboardButton("Убрать", callback_data=f"remove_{product_name}_{price}_{catalog_name}")
    buttons.append(remove_button)

    if count > 0:
        cart_button = types.InlineKeyboardButton(f"Оформить: {count}", callback_data="show_cart")
        buttons.append(cart_button)


    else:

        add_to_cart_button = types.InlineKeyboardButton("В корзину",
                                                        callback_data=f"addtocart_{product_name}_{catalog_name}_{price}")
        buttons = [add_to_cart_button]

    return buttons


async def update_product_buttons(callback_query, product_name, catalog_name, user_id, price=0):
    count = await get_cart_quantity(user_id, product_name)

    buttons = await generate_cart_buttons(
        product_name, catalog_name, user_id, price, count
    )

    back_button = InlineKeyboardButton("Назад", callback_data="show_catalog")

    await bot.edit_message_reply_markup(
        user_id,
        message_id=callback_query.message.message_id,
        reply_markup=InlineKeyboardMarkup(row_width=2).add(*buttons).add(back_button)
    )


async def get_cart_quantity(user_id, product_name):
    user_cart = user_carts.get(user_id, {})

    if product_name in user_cart:
        return user_cart[product_name]['quantity']
    else:
        return 0


# Корзина
@dp.callback_query_handler(lambda c: c.data == 'show_cart')
async def show_cart(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_cart = user_carts.get(user_id, {})

    if not user_cart:
        await callback_query.answer("Ваша корзина пуста.", show_alert=True)
        return

    items = []
    total_price = 0

    for product_name, product_data in user_cart.items():
        quantity = product_data['quantity']
        price = product_data['price']
        total_price += quantity * price
        items.append(f"{product_name}: {quantity} шт. - {price * quantity} сом")

    text = f"Содержимое корзины:\n\n" + "\n".join(items) + f"\n\nИтого: {total_price} сом"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💲 Оформить заказ", callback_data="checkout"))
    markup.add(InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="назад"))

    if callback_query.message.text:
        await bot.edit_message_text(text, user_id, callback_query.message.message_id, reply_markup=markup)
    else:
        await bot.send_message(user_id, text, reply_markup=markup)

    user_carts[user_id] = user_cart


def calculate_total_price(user_id):
    user_cart = user_carts.get(user_id, {})
    total_price = sum(product_data['quantity'] * product_data['price'] for product_data in user_cart.values())
    return total_price


def get_cart_sum(user_id):
    user_cart = user_carts.get(user_id, {})
    total_quantity = sum(product_data['quantity'] for product_data in user_cart.values())
    return total_quantity


@dp.callback_query_handler(lambda c: c.data == "checkout")
async def checkout(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    user_in_black_list = await get_blacklist_info(user_id)
    user_info = await get_user(user_id)
    user_cart = user_carts.get(user_id, {})

    if not user_cart:
        await bot.send_message(user_id, "Ваша корзина пуста. Оформление заказа невозможно.")
        return

    if not user_in_black_list:
        if user_info:
            await SetDeliveryState.waiting_for_delivery.set()

            markup = types.InlineKeyboardMarkup()
            pickup_button = types.InlineKeyboardButton("Самовывоз", callback_data="Самовывоз")
            delivery_button = types.InlineKeyboardButton("Доставка курьером", callback_data="Доставка курьером")
            markup.add(pickup_button, delivery_button)
            markup.add(InlineKeyboardButton("Назад", callback_data='canceldelivery'))
            await bot.edit_message_text("Выберите способ доставки:", user_id,
                                        callback_query.message.message_id,
                                        reply_markup=markup)
        else:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton('📝 Регистрация ℹ', callback_data="register_new"))
            keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data="назад"))
            await bot.edit_message_text("ℹ Для оформления заказа необходимо зарегистрироваться.",
                                        callback_query.from_user.id,
                                        callback_query.message.message_id,
                                        reply_markup=keyboard)
    else:
        await bot.edit_message_text("Вы в черном списке, свяжитесь с администрацией", user_id,
                                    callback_query.message.message_id,
                                    reply_markup=menu_keyboard)


@dp.callback_query_handler(lambda c: c.data == 'canceldelivery', state=SetDeliveryState.waiting_for_delivery)
async def canceldelivery(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    await bot.edit_message_text('✅ Действие отменено', user_id, callback_query.message.message_id,
                                reply_markup=menu_keyboard)
    await state.finish()


@dp.callback_query_handler(lambda callback_query: callback_query.data == "register_new")
async def register_start(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Отмена', callback_data='canceladdnewname'))
    await bot.edit_message_text("✍ Введите имя:", user_id,
                                callback_query.message.message_id,
                                reply_markup=keyboard)
    await AddNewPerson.add_name.set()

    @dp.message_handler(lambda message: message.text and not re.match(r'^[0-9\+\-\(\)]+$', message.text),
                        state=AddNewPerson.add_name)
    async def register_name(message: types.Message, state: FSMContext):
        async with state.proxy() as data:
            data['name'] = message.text

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton('Отмена', callback_data='canceladdnewnumber'))
        await message.answer(
            "✅ Имя сохранено. Теперь введите номер телефона:\nПример:\n0999-123-456\n0999123456", reply_markup=keyboard)
        await AddNewPerson.add_number.set()

    @dp.message_handler(lambda message: not ''.join(filter(str.isdigit, message.text)), state=AddNewPerson.add_number)
    async def handle_non_digit_input(message: types.Message):
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton('Отмена', callback_data='canceladdnewnumber'))
        await message.answer("❌ Некорректный ввод. Пожалуйста, введите только цифры.", reply_markup=keyboard)
        await bot.edit_message_text(
            "❌ Некорректный ввод.\nПожалуйста, введите только цифры.\nПример:\n0999123456",
            message.from_user.id,
            message.message_id,
            reply_markup=keyboard
        )

    @dp.message_handler(lambda message: re.match(r'^[0-9\(\)]+$', message.text), state=AddNewPerson.add_number)
    async def register_number(message: types.Message, state: FSMContext):
        async with state.proxy() as data:
            data['number'] = ''.join(filter(str.isdigit, message.text))
        text = "❌ Некорректный ввод.\nПожалуйста, введите только цифры.\nПример:\n0999123456\nДолжно быть более 9 цифр"
        if len(data['number']) < 9:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton('Отмена', callback_data='canceladdnewnumber'))
            await message.answer(text, reply_markup=keyboard)
            return

        user_id = message.from_user.id
        name = data['name']
        number = data['number']
        await add_user(user_id, name, number)

        await state.finish()

        keyboard_get_katalog = InlineKeyboardMarkup()
        keyboard_get_katalog.add(InlineKeyboardButton('🛄 Перейти к оформлению', callback_data="checkout"))
        keyboard_get_katalog.add(InlineKeyboardButton('🔙 Назад', callback_data="назад"))
        await message.reply('✅ Регистрация завершена. Ваши данные обновлены!', reply_markup=keyboard_get_katalog)


@dp.callback_query_handler(lambda c: c.data == 'canceladdnewname', state=AddNewPerson.add_name)
async def canceladdnewname(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    await bot.edit_message_text('✅ Действие отменено', user_id, callback_query.message.message_id,
                                reply_markup=menu_keyboard)
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == 'canceladdnewnumber', state=AddNewPerson.add_number)
async def canceladdnewnumber(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    await bot.edit_message_text('✅ Действие отменено', user_id, callback_query.message.message_id,
                                reply_markup=menu_keyboard)
    await state.finish()


def calculate_total_price(user_id):
    user_cart = user_carts.get(user_id, {})
    total_price = sum(product_data['quantity'] * product_data['price'] for product_data in user_cart.values())
    return total_price


@dp.callback_query_handler(lambda c: c.data == "Самовывоз" or c.data == "Доставка курьером",
                           state=SetDeliveryState.waiting_for_delivery)
async def process_delivery(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    delivery_type = callback_query.data
    user_cart = user_carts.get(user_id, {})
    catalog_name = catalog_name_data.get(user_id)
    total_price = calculate_total_price(user_id)
    if not user_cart:
        await bot.edit_message_text("Ваша корзина пуста. Оформление заказа невозможно.", user_id,
                                    callback_query.message.message_id,
                                    reply_markup=menu_keyboard)
        return

    if delivery_type == "Самовывоз":
        pickup_address = await get_pickup_address()
        if pickup_address:
            await state.finish()
            order_id = await save_order(user_id, "Самовывоз", total_price, user_cart, catalog_name,
                                        pickup_address.get("pickup"))
            text = f'✅ Спасибо за ваш заказ!\nВы сможете забрать заказ по адресу:\n'
            text += f'➖➖➖➖➖➖➖\n'
            text += f'{pickup_address.get("pickup")}\n'
            text += f'➖➖➖➖➖➖➖\n'
            text += f"Оператор свяжется с вами для подтверждения деталей.\nВаш номер заказа:\n{order_id}"
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton('Назад', callback_data='назад'))
            await bot.edit_message_text(text, user_id, callback_query.message.message_id,
                                        reply_markup=keyboard)
            await send_order_to_admins(user_id, user_cart, total_price, "Самовывоз", order_id,
                                       pickup_address.get("pickup"))
            user_carts.pop(user_id, None)
        else:
            await state.finish()
            await callback_query.message.edit_text("Адрес самовывоза не указан. Обратитесь к администратору.",
                                                   user_id, callback_query.message.message_id,
                                                   reply_markup=menu_keyboard)
    elif delivery_type == "Доставка курьером":
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Отмена", callback_data="cancel_delivery"))
        await bot.edit_message_text("Укажите адрес доставки:", user_id,
                                    callback_query.message.message_id, reply_markup=keyboard)
        await DeliveryState.waiting_for_address.set()

        @dp.message_handler(state=DeliveryState.waiting_for_address)
        async def process_delivery_address(message: types.Message, state: FSMContext):
            delivery_address = message.text
            user_id = message.from_user.id
            await state.finish()
            order_id = await save_order(user_id, "Доставка курьером", total_price, user_cart, catalog_name,
                                        delivery_address)
            await send_order_to_admins(user_id, user_cart, total_price, "Доставка курьером", order_id, delivery_address)
            text = "✅ Спасибо за ваш заказ!\n"
            text += f"Ваш номер заказа:\n{order_id}\n"
            text += f'Вы указали адрес доставки:\n'
            text += f'➖➖➖➖➖➖➖\n'
            text += f'{delivery_address}\n'
            text += f'➖➖➖➖➖➖➖\n'
            text += f'Оператор свяжется с вами для подтверждения деталей.\n'
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton('Назад', callback_data='назад'))
            await message.answer(text, reply_markup=keyboard)
            user_carts.pop(user_id, None)


@dp.callback_query_handler(lambda c: c.data == "cancel_delivery", state=DeliveryState.waiting_for_address)
async def cancel_delivery(callback_query: CallbackQuery, state: FSMContext):
    await bot.edit_message_text("❗🔑 Что делаем дальше❓", callback_query.from_user.id,
                                callback_query.message.message_id, reply_markup=menu_keyboard)
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "clear_cart")
async def clear_user_cart(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    user_carts.pop(user_id, None)
    await state.finish()
    await bot.edit_message_text("Корзина очищена.", user_id, callback_query.message.message_id,
                                reply_markup=menu_keyboard)


async def send_order_to_admins(user_id, user_cart, total_price, delivery_type, order_id, delivery_address):
    admin_chat_id = GROUP_CHAT_ID
    user_info = await get_user(user_id)
    user = await bot.get_chat(user_id)
    username = user.username
    formatted_time = order_time.strftime("%Y-%m-%d %H:%M:%S")
    if not user_info:
        return

    text = f"Новый заказ от пользователя\nt.me/{username}\n"
    text += f"ID: {user_id}\n"
    text += f"Номер заказа:\n{order_id}\n"
    text += f"Имя: {user_info['name']}\n"
    text += f"Тел.номер: {user_info['number']}\n"
    text += f"Время заказа: {formatted_time}\n"
    text += f"Способ доставки: {delivery_type}\n"
    if delivery_type == "Доставка курьером":
        text += f"Адрес доставки:\n{delivery_address}\n"
    elif delivery_type == "Самовывоз":
        text += f"Пункт выдачи:\n{delivery_address}\n"
    text += "Заказанные товары:\n"

    for product_name, product_data in user_cart.items():
        text += f"➖ {product_name}: {product_data['quantity']} шт. | {product_data['price'] * product_data['quantity']} сом\n"

    text += f"Итого: {total_price} сом"

    await bot.send_message(admin_chat_id, text)


@dp.callback_query_handler(text="show_orders")
async def show_orders(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    order_history = await get_order_history(user_id)
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Главное меню', callback_data="назад"))
    count_products = 0
    count_price = 0
    if not order_history:
        await callback_query.answer("Вы еще не делали заказов", show_alert=True)
        return
    else:
        for order in order_history:
            order_info = (
                f"Заказ:\nNo{order['_id']}:\n"
                f"Способ доставки: {order['delivery_type']}\n"
                f"Итоговая цена: {order['total_price']} сом\n"
                f"Время заказа: {order['order_time']}\n"
                "Товары в заказе:\n"
            )
            count_products += 1
            count_price += float(order['total_price'])
            for product_name, product_data in order['products'].items():
                quantity = product_data['quantity']
                price = product_data['price']
                order_info += f"{product_name}: {quantity} шт. - {price} сом\n"

            await bot.send_message(user_id, order_info)
        await bot.send_message(user_id, f'Всего заказов {count_products} на сумму {count_price}',
                               reply_markup=keyboard)



@dp.callback_query_handler(text="show_profile", state="*")
async def show_profile(callback_query: types.CallbackQuery, state=FSMContext):
    user_id = callback_query.from_user.id
    admin_user_ids = admin_user_id
    admin_user_ids.extend(await get_admins_ids_from_db())

    await state.finish()

    if callback_query.from_user.id in admin_user_ids:
        async def get_admin_inline_keyboard():
            admin_inline_keyboard = InlineKeyboardMarkup(row_width=2)
            admins = InlineKeyboardButton("🤴 Администрирование", callback_data="admins")
            catalogsandproduct = InlineKeyboardButton("👀 Каталоги и Товары", callback_data="catalogsandproduct")
            main_menu_show = InlineKeyboardButton("🏃🏻‍♀️ Главное меню", callback_data="назад")
            admin_inline_keyboard.add(admins)
            admin_inline_keyboard.add(catalogsandproduct)
            admin_inline_keyboard.add(main_menu_show)
            return admin_inline_keyboard

        text = "🔑 Вы вошли как администратор"
        await bot.edit_message_text(text, user_id, callback_query.message.message_id,
                                    reply_markup=await get_admin_inline_keyboard())

        @dp.callback_query_handler(lambda c: c.data == "contacts")
        async def process_contacts(callback_query: CallbackQuery):
            messengers = await get_messanger_from_db()

            if not messengers:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🤌 Добавить", callback_data="addcontact"))
                keyboard.add(InlineKeyboardButton("🏃🏻‍♀️ Назад", callback_data="admins"))
                await bot.edit_message_text(
                    "У вас пока нет контактов. Хотите добавить?",
                    callback_query.from_user.id,
                    callback_query.message.message_id,
                    reply_markup=keyboard
                )
            else:
                await show_contacts(callback_query)

        async def show_contacts(callback_query: CallbackQuery):
            messengers = await get_messanger_from_db()
            keyboard = InlineKeyboardMarkup()

            for messenger in messengers:
                name = messenger.get("name", {}).get("name", "")
                link = messenger.get("name", {}).get("link", "")
                button = InlineKeyboardButton(f"{name.capitalize()}: {link}", callback_data=f"contact_{name}")
                keyboard.add(button)

            keyboard.add(
                InlineKeyboardButton("👷 Добавить", callback_data="addcontact"),
                InlineKeyboardButton("🕵️‍♂️ Удалить", callback_data="deletecontact")
            )
            keyboard.add(InlineKeyboardButton("🏃🏻‍♀️ Назад", callback_data="admins"))

            await bot.edit_message_text(
                "👥 Контакты:",
                callback_query.from_user.id,
                callback_query.message.message_id,
                reply_markup=keyboard
            )

        @dp.callback_query_handler(lambda c: c.data == "deletecontact")
        async def delete_contact(callback_query: CallbackQuery):
            messengers = await get_messanger_from_db()
            keyboard = InlineKeyboardMarkup()

            for messenger in messengers:
                name = messenger.get("name", {}).get("name", "")
                link = messenger.get("name", {}).get("link", "")
                button = InlineKeyboardButton(f"{str(name).capitalize()}",
                                              callback_data=f"deletecontact_{str(name).strip()}")
                keyboard.add(button)

            keyboard.add(InlineKeyboardButton("Отмена", callback_data="admins"))
            await bot.edit_message_text(
                "Выберите контакт для удаления:",
                callback_query.from_user.id,
                callback_query.message.message_id,
                reply_markup=keyboard
            )

        @dp.callback_query_handler(lambda c: c.data.startswith("deletecontact_"))
        async def confirm_delete(callback_query: CallbackQuery):
            name = callback_query.data.split("_")[1].strip()
            all_contacts = await get_messanger_from_db()
            await remove_contact_from_db(name)

            await bot.edit_message_text(
                f"Контакт {name} удален",
                callback_query.from_user.id,
                callback_query.message.message_id,
                reply_markup=await get_admin_inline_keyboard()
            )

        @dp.callback_query_handler(lambda c: c.data == "addcontact")
        async def add_contact(callback: CallbackQuery):
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Отмена", callback_data="admins"))
            await bot.edit_message_text(
                "Введите название мессенджера:",
                callback.from_user.id,
                callback.message.message_id,
                reply_markup=keyboard
            )
            await AddContactState.waiting_for_contact.set()

        @dp.message_handler(state=AddContactState.waiting_for_contact)
        async def add_contact_name(message: types.Message, state: FSMContext):
            name = message.text.lower()
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Отмена", callback_data="admins"))
            await message.answer("Введите данные контакта (номер, ссылку и т.д.):", reply_markup=keyboard)
            await state.update_data(name=name)
            await AddContactState.next()

        @dp.message_handler(state=AddContactState.waiting_for_messanger)
        async def add_contact_data(message: types.Message, state: FSMContext):
            data = await state.get_data()
            name = data.get("name")
            contact_data = message.text

            new_contact = {
                "name": name,
                "link": contact_data
            }

            await addmessanger(new_contact)

            await state.finish()
            await message.answer(
                f"Контакт {name} добавлен!",
                reply_markup=await get_admin_inline_keyboard()
            )

        @dp.callback_query_handler(lambda c: c.data == "get_pickup_address")
        async def get_pickup_address_handler(callback_query: CallbackQuery):
            address = await get_pickup_address()

            if address:
                text = f"Адрес самовывоза: {address.get('pickup')}"
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🗣 Изменить", callback_data="updateadress"))
                keyboard.add(InlineKeyboardButton("🏃🏻‍♀️ Назад", callback_data="admins"))
                await bot.edit_message_text(text, callback_query.from_user.id, callback_query.message.message_id,
                                            reply_markup=keyboard)
            else:
                text = "Адрес отсутствует, добавьте новый адрес"
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🗣 Добавить", callback_data="addpickup_address"))
                keyboard.add(InlineKeyboardButton("🏃🏻‍♀️ Назад", callback_data="admins"))
                await bot.edit_message_text(text, callback_query.from_user.id, callback_query.message.message_id,
                                            reply_markup=keyboard)

        @dp.callback_query_handler(lambda c: c.data == "addpickup_address", state="*")
        async def addpickup_address(callback_query: CallbackQuery):
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Отмена", callback_data="admins"))
            await bot.edit_message_text(
                "Введите адрес самовывоза:",
                callback_query.from_user.id,
                callback_query.message.message_id,
                reply_markup=keyboard
            )
            await PickupAddressState.waiting_for_address.set()

        @dp.message_handler(state=PickupAddressState.waiting_for_address)
        async def process_pickup_address(message: types.Message, state: FSMContext):
            pickup_address = message.text

            await add_pickup_address(pickup_address)

            await state.finish()
            await bot.send_message(
                message.from_user.id,
                f"Адрес самовывоза успешно сохранен: {pickup_address}",
                reply_markup=await get_admin_inline_keyboard()
            )

        @dp.callback_query_handler(lambda c: c.data == "updateadress")
        async def update_address(callback_query: CallbackQuery):
            await bot.send_message(callback_query.from_user.id, "🐌 Введите новый адрес для обновления:")
            await UpdateAddressState.waiting_for_new_address.set()

        @dp.message_handler(state=UpdateAddressState.waiting_for_new_address)
        async def process_new_address(message: types.Message, state: FSMContext):
            new_address = message.text
            await update_pickup_address(new_address)
            await state.finish()
            await bot.send_message(message.from_user.id, f"🧳 Адрес самовывоза успешно обновлен: {new_address}",
                                   reply_markup=await get_admin_inline_keyboard())

        @dp.callback_query_handler(lambda c: c.data == "send_message")
        async def send_message_to_all(callback: CallbackQuery):
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="admins"))
            await bot.edit_message_text(
                "Введите текст рассылки:",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)
            await Broadcast.waiting_text.set()

        @dp.message_handler(state=Broadcast.waiting_text)
        async def set_broadcast_text(message: types.Message, state: FSMContext):
            confirm_keyboard = InlineKeyboardMarkup(row_width=2)
            confirm_button = InlineKeyboardButton(text="🤷‍♂️ Да", callback_data="confirm_yes")
            cancel_button = InlineKeyboardButton(text="🏃‍♂️ Отмена", callback_data="admins")
            confirm_keyboard.add(confirm_button, cancel_button)
            await state.update_data(text=message.text)

            await message.answer("🕶 Отправить рассылку?", reply_markup=confirm_keyboard)

        @dp.callback_query_handler(text="confirm_no", state=Broadcast.waiting_text)
        async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
            await callback.message.answer("👌 Отменено", reply_markup=await get_admin_inline_keyboard())
            await state.finish()

        @dp.callback_query_handler(text="confirm_yes", state=Broadcast.waiting_text)
        async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
            data = await state.get_data()
            text = data.get("text")
            users = await get_users_from_db()
            successful_count = 0

            for user in users:
                try:
                    await bot.send_message(user["user_id"], text)
                    successful_count += 1
                except ChatNotFound:
                    pass
            await bot.send_message(callback.from_user.id, "Главное меню", reply_markup=menu_keyboard)

            await callback.message.answer(
                f"🕶 Рассылка выполнена!\nУспешно отправлено {successful_count} сообщений.",
                reply_markup=await get_admin_inline_keyboard()
            )
            await state.finish()

        # Перезапуск бота, если вы сменили название файла запуска, то измените название main.py на своё
        @dp.callback_query_handler(lambda c: c.data == 'restart_bot')
        async def confirm_restart(callback_query: types.CallbackQuery):
            keyboard = InlineKeyboardMarkup()
            confirm_button = InlineKeyboardButton("🚸 Да, перезапустить", callback_data='confirm_restart')
            cancel_button = InlineKeyboardButton("☄️ Отмена", callback_data='admins')
            keyboard.add(confirm_button, cancel_button)
            await bot.edit_message_text(
                "🤦‍♀️ Вы уверены, что хотите перезапустить бота?",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)

        @dp.callback_query_handler(lambda c: c.data == 'confirm_restart')
        async def restart_bot(callback_query: types.CallbackQuery):
            await callback_query.answer("💆‍♀️ Перезапускаю бота...\nОжидайте минуточку...", show_alert=True)
            await dp.storage.close()
            await dp.storage.wait_closed()
            subprocess.run("python main.py", shell=True)

        @dp.callback_query_handler(lambda c: c.data == 'cancel_restart')
        async def cancel_restart(callback_query: types.CallbackQuery):
            await bot.edit_message_text(
                "🕺 Перезапуск отменен.",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=await get_admin_inline_keyboard())

        async def get_addproduct_keyboard():
            catalogs = await get_categories_from_db()
            keyboard = InlineKeyboardMarkup()

            for category in catalogs:
                category_name = category.get('name', 'Нет имени')
                cleaned_category_name = re.sub(r'\W', '-', category_name)
                category_button_text = f"{category_name}"
                button = InlineKeyboardButton(category_button_text,
                                              callback_data=f"catalog_{cleaned_category_name}")
                keyboard.add(button)

            return keyboard

        @dp.callback_query_handler(lambda callback_query: callback_query.data == "admins", state='*')
        async def admins_keyboard(callback_query: types.CallbackQuery, state=FSMContext):
            await state.finish()
            text = "Выберите действие"
            keyboard = InlineKeyboardMarkup(row_width=2)
            addmin = InlineKeyboardButton('🧑‍✈️ Добавить админа', callback_data="addadmin_")
            delmin = InlineKeyboardButton('☠️ Удалить админа', callback_data="listadmins_")
            add_black_list = InlineKeyboardButton("🤡 Добавить в чс", callback_data="addblacklist_")
            del_black_list = InlineKeyboardButton("🤐 Убрать из чс", callback_data="blacklist_")
            contactadd = InlineKeyboardButton("📞 Контакты", callback_data="contacts")
            adress = InlineKeyboardButton("🛬 Адрес", callback_data="get_pickup_address")
            stats = InlineKeyboardButton('📈 Статистика', callback_data="stats")
            send_message_to_all = InlineKeyboardButton("📢 Рассылка", callback_data="send_message")
            # user_info_page = InlineKeyboardButton('🪪 Люди', callback_data="select_user")
            restart_bot = InlineKeyboardButton('🫡 Хотите перезагрузить бота?', callback_data="restart_bot")
            keyboard.add(addmin, delmin)
            keyboard.add(add_black_list, del_black_list)
            keyboard.add(adress, contactadd)
            keyboard.add(send_message_to_all, stats)
            # keyboard.add(user_info_page)
            keyboard.add(restart_bot)
            keyboard.add(InlineKeyboardButton('Назад', callback_data="show_profile"))
            await bot.edit_message_text(text,
                                        callback_query.from_user.id,
                                        callback_query.message.message_id,
                                        reply_markup=keyboard
                                        )

        @dp.callback_query_handler(lambda callback_query: callback_query.data == "catalogsandproduct", state='*')
        async def admins_keyboard(callback_query: types.CallbackQuery, state: FSMContext):
            text = "Хотите добавить каталог или товар?"
            keyboard = InlineKeyboardMarkup(row_width=2)
            catalog = InlineKeyboardButton("Добавить каталог🌚", callback_data="addcategory_")
            delcatalog = InlineKeyboardButton("🌝Удалить каталог", callback_data="deletecategory_")
            addproduct = InlineKeyboardButton("Добавить товар👉", callback_data="addproduct_")
            delproduct = InlineKeyboardButton("👈Удалить товар", callback_data="deleteproduct_")
            editor = InlineKeyboardButton("🤝 Редактировать товары", callback_data='editproduct_')
            keyboard.add(catalog, delcatalog)
            keyboard.add(addproduct, delproduct)
            keyboard.add(editor)
            keyboard.add(InlineKeyboardButton('🏃🏻‍♀️ Назад', callback_data="show_profile"))
            await bot.edit_message_text(text,
                                        callback_query.from_user.id,
                                        callback_query.message.message_id,
                                        reply_markup=keyboard
                                        )
            await state.finish()

        @dp.callback_query_handler(lambda c: c.data == "editproduct_", state="*")
        async def choose_category_for_edit(callback_query: types.CallbackQuery):
            categories = await get_categories_from_db()

            if not categories:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='catalogsandproduct'))
                await bot.edit_message_text(
                    "Нет доступных категорий для редактирования товаров.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)
                return

            keyboard = InlineKeyboardMarkup()
            for category in categories:
                category_name = category.get("name", "Без названия")
                keyboard.add(InlineKeyboardButton(category_name, callback_data=f"editproduct_{category_name}"))

            keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='catalogsandproduct'))

            await bot.edit_message_text(
                "Выберите категорию для редактирования товаров:",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)
            await EditProduct.select_category.set()

        @dp.callback_query_handler(lambda c: c.data.startswith("editproduct_"), state=EditProduct.select_category)
        async def choose_product_category_for_edit(callback_query: types.CallbackQuery, state: FSMContext):
            selected_category = callback_query.data.split('_')[1]
            products = await get_products_in_category(selected_category)

            if not products:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔁 Выберите другую категорию?", callback_data="editproduct_"))
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='catalogsandproduct'))
                await bot.edit_message_text(
                    "В этой категории нет товаров для редактирования.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)
                await state.finish()
                return

            product_buttons = []
            for product in products:
                product_name = product['product_name']
                product_buttons.append(
                    InlineKeyboardButton(product_name,
                                         callback_data=f"editconfirmed_{selected_category}_{product_name}")
                )

            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(*product_buttons)
            keyboard.add(InlineKeyboardButton("🔙 Передумали ?", callback_data='catalogsandproduct'))

            await state.update_data(selected_category=selected_category, product_name=product_name)
            await EditProduct.select_product.set()

            await bot.edit_message_text(
                "Выберите товар для редактирования:",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard
            )

        @dp.callback_query_handler(lambda c: c.data.startswith("editconfirmed_"), state=EditProduct.select_product)
        async def edit_confirmed(callback_query: types.CallbackQuery, state: FSMContext):
            state_data = await state.get_data()
            selected_category = state_data.get('selected_category')
            data_parts = callback_query.data.split("_")
            product_name = data_parts[2]
            product = await get_product_by_name(product_name)

            if product:
                name_description = product.get('name_description', 'Нет данных')
                product_price = product.get('product_price', 'Нет данных')
                quantity = product.get('quantity', 'Нет данных')

                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    InlineKeyboardButton(f"{product_name}",
                                         callback_data=f"edit_attribute_{selected_category}_{product_name}_name"),
                    InlineKeyboardButton(f"{name_description}",
                                         callback_data=f"edit_attribute_{selected_category}_{product_name}_description"),
                    InlineKeyboardButton(f"{product_price}",
                                         callback_data=f"edit_attribute_{selected_category}_{product_name}_price"),
                    InlineKeyboardButton(f"{quantity}",
                                         callback_data=f"edit_attribute_{selected_category}_{product_name}_quantity"),
                    InlineKeyboardButton("🔙 Назад", callback_data='catalogsandproduct')
                )
                await bot.send_message(callback_query.from_user.id, "Выберите, что вы хотите изменить:",
                                       reply_markup=keyboard)
                await EditProduct.select_attribute.set()
            else:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton("🔁 Попробуйте снова", callback_data=f"editproduct_{selected_category}"))
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='catalogsandproduct'))
                await bot.edit_message_text(
                    "Произошла ошибка при редактировании товара. Возможно, товар не найден.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard
                )

        @dp.callback_query_handler(lambda c: c.data.startswith("edit_attribute_"), state=EditProduct.select_attribute)
        async def edit_attribute(callback_query: types.CallbackQuery, state: FSMContext):
            state_data = await state.get_data()
            selected_category = state_data.get('selected_category')
            product_name = state_data.get('product_name')
            name_description = state_data.get("name_description")
            product_price = state_data.get("product_price")
            quantity = state_data.get("quantity")
            data_parts = callback_query.data.split("_")
            attribute = data_parts[-1]
            attribute_mapping = {
                'price': 'Цены',
                'description': 'Описания',
                'name': 'Названия',
                'quantity': 'Количества'
            }
            new_name = attribute_mapping.get(attribute, attribute)
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='catalogsandproduct'))
            if not attribute:
                print("Error: attribute is None")
                return

            await bot.send_message(callback_query.from_user.id,
                                   f"Введите новое значение для {new_name} товара {product_name}:",
                                   reply_markup=keyboard)
            await state.update_data(selected_attribute=attribute)
            await EditProduct.enter_new_data.set()

        @dp.message_handler(state=EditProduct.enter_new_data)
        async def process_new_data(message: types.Message, state: FSMContext):
            new_data = message.text
            state_data = await state.get_data()
            selected_category = state_data.get('selected_category')
            product_name = state_data.get('product_name')
            selected_attribute = state_data.get('selected_attribute')

            keyboard = InlineKeyboardMarkup()
            catalogsandproduct = InlineKeyboardButton('Изменить еще?', callback_data='editproduct_')
            cancel = InlineKeyboardButton("🔙 Назад", callback_data='catalogsandproduct')
            keyboard.add(catalogsandproduct)
            keyboard.add(cancel)
            attribute_mapping = {
                'price': 'product_price',
                'description': 'name_description',
                'name': 'product_name',
                'quantity': 'quantity'
            }

            attribute = attribute_mapping.get(selected_attribute, selected_attribute)

            if attribute == 'product_name':
                new_data = ''.join(word.capitalize() for word in new_data.split())

            try:
                await update_product_in_catalog(selected_category, product_name, {attribute: new_data})
                await message.reply("Информация о товаре успешно обновлена.", reply_markup=keyboard)
            except Exception as e:
                await message.reply(f"Произошла ошибка при обновлении информации о товаре: {e}", reply_markup=keyboard)

            await state.finish()

        # Добавить админа
        @dp.callback_query_handler(lambda callback_query: callback_query.data == "addadmin_")
        async def add_admin_select_user(callback_query: types.CallbackQuery, state: FSMContext):
            users = await get_users_from_db()

            if users:
                keyboard = InlineKeyboardMarkup()
                for user in users:
                    user_id = user['user_id']
                    user_name = user.get('name', 'Нет имени')
                    user_number = user.get('number', 'Нет номера')
                    button_text = f"ID:{user_id},🎫 {user_name},🗿 {user_number}"
                    button = InlineKeyboardButton(button_text, callback_data=f"select_user_{user_id}")
                    keyboard.add(button)
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='admins'))
                await bot.edit_message_text("🎖 Выберите пользователя, которого вы хотите добавить в администраторы:",
                                            callback_query.from_user.id, callback_query.message.message_id,
                                            reply_markup=keyboard)
                await UserForm.add_admin.set()
            else:
                await bot.send_message(callback_query.from_user.id, "Список пользователей пуст.",
                                       reply_markup=await get_admin_inline_keyboard())

        @dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('select_user_'),
                                   state=UserForm.add_admin)
        async def select_user_for_admin(callback_query: types.CallbackQuery, state: FSMContext):
            user_id = int(callback_query.data.split('_')[2])
            user = await get_user(user_id)

            if user:
                user_name = user.get('name', 'Нет имени')
                user_number = user.get('number', 'Нет номера')

                await state.update_data(admin_id=user_id, user_name=user_name,
                                        user_number=user_number)

                user_data = await state.get_data()
                user_id = user_data['admin_id']
                user_name = user_data['user_name']
                user_number = user_data['user_number']

                inserted_id = await add_admin_to_db(user_id, user_name, user_number)

                keyboard = InlineKeyboardMarkup()

                if inserted_id:
                    keyboard.add(InlineKeyboardButton('🔁 Добавить еще', callback_data="addadmin_"))
                    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='admins'))
                    await bot.edit_message_text(
                        f"Пользователь с ID {user_id}, именем '{user_name}' и номером '{user_number}' добавлен в список администраторов.",
                        callback_query.from_user.id, callback_query.message.message_id,
                        reply_markup=keyboard)
                else:
                    keyboard.add(InlineKeyboardButton('🔁 Попробовать снова?', callback_data="addadmin_"))
                    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='admins'))
                    await bot.edit_message_text(
                        f"Пользователь с ID {user_id} уже является администратором или произошла ошибка.",
                        callback_query.from_user.id, callback_query.message.message_id,
                        reply_markup=keyboard)

                await state.finish()

        # Добавить в чс
        @dp.callback_query_handler(lambda callback_query: callback_query.data == "addblacklist_")
        async def add_black_list_select_user(callback_query: types.CallbackQuery, state: FSMContext):
            users = await get_users_from_db()

            if users:
                keyboard = InlineKeyboardMarkup()
                for user in users:
                    user_id = user['user_id']
                    user_name = user.get('name', 'Нет имени')
                    user_number = user.get('number', 'Нет номера')
                    button_text = f"ID:{user_id},🎫{user_name},🗿{user_number}"
                    button = InlineKeyboardButton(button_text, callback_data=f"select_user_{user_id}")
                    keyboard.add(button)
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='admins'))
                await bot.edit_message_text(
                    "Выберите пользователя, которого вы хотите добавить в черный список:",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)
                await UserForm.black_list.set()
            else:
                await bot.edit_message_text(
                    "Список пользователей пуст.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=await get_admin_inline_keyboard())

        @dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('select_user_'),
                                   state=UserForm.black_list)
        async def select_user_for_admin(callback_query: types.CallbackQuery, state: FSMContext):
            user_id = int(callback_query.data.split('_')[2])
            user = await get_user(user_id)

            if user:
                user_name = user.get('name', 'Нет имени')
                user_number = user.get('number', 'Нет номера')

                await state.update_data(admin_id=user_id, user_name=user_name,
                                        user_number=user_number)

                user_data = await state.get_data()
                user_id = user_data['admin_id']
                user_name = user_data['user_name']
                user_number = user_data['user_number']

                inserted_id = await add_user_to_black_list(user_id, user_name, user_number)

                keyboard = InlineKeyboardMarkup()

                if inserted_id:
                    keyboard.add(InlineKeyboardButton('🔁 Добавить еще', callback_data="addblacklist_"))
                    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='admins'))
                    await bot.edit_message_text(
                        f"Пользователь с ID {user_id}, именем '{user_name}' и номером '{user_number}' добавлен в черный список.",
                        callback_query.from_user.id, callback_query.message.message_id,
                        reply_markup=keyboard)


                else:
                    keyboard.add(InlineKeyboardButton('🔁 Попробовать снова?', callback_data="addblacklist_"))
                    keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='admins'))
                    await bot.edit_message_text(
                        f"Пользователь с ID {user_id} уже в черном списке или произошла ошибка.",
                        callback_query.from_user.id, callback_query.message.message_id,
                        reply_markup=keyboard)

                await state.finish()

        # Удалить админа
        @dp.callback_query_handler(lambda callback_query: callback_query.data == "listadmins_")
        async def list_admins(callback_query: types.CallbackQuery):
            admins_info = await get_admins_from_db()
            if not admins_info:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='admins'))
                await bot.edit_message_text(
                    "Список администраторов пуст.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)
            else:
                keyboard = InlineKeyboardMarkup()
                for admin in admins_info:
                    user_id = admin['user_id']
                    user_name = admin.get('user_name', 'Нет имени')
                    user_number = admin.get('user_number', 'Нет номера')
                    button_text = f"👥:{user_name}\n📞:{user_number}"
                    button = InlineKeyboardButton(button_text, callback_data=f"delete_admin_{user_id}")
                    keyboard.add(button)
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='admins'))
                await bot.edit_message_text(
                    "Список администраторов:",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)

        @dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('delete_admin_'))
        async def delete_admin(callback_query: types.CallbackQuery):
            user_id = int(callback_query.data.split('_')[2])

            admin_info = await get_admin_info(user_id)
            user_info = await get_user(user_id)

            admin_name = 'Нет имени'
            admin_number = 'Нет номера'
            keyboard = InlineKeyboardMarkup()

            if admin_info:
                admin_name = admin_info.get('user_name', admin_name)
                admin_number = admin_info.get('user_number', admin_number)

            user_name = 'Нет имени'
            user_number = 'Нет номера'

            if user_info:
                user_name = user_info.get('name', user_name)
                user_number = user_info.get('number', user_number)

            if admin_info:
                keyboard.add(InlineKeyboardButton('🔁 Еще кого то удаляем ❓', callback_data="listadmins_"))
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='admins'))
                await remove_admin_from_db(user_id)
                await bot.edit_message_text(
                    f"Администратор {user_name} (ID: {user_id}) удален.",
                    chat_id=callback_query.from_user.id,
                    message_id=callback_query.message.message_id, reply_markup=keyboard)
            else:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton('🔁 Еще кого то удаляем ❓', callback_data="listadmins_"))
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='admins'))
                await bot.edit_message_text(
                    f"Администратор (ID: {user_id}) не найден.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)

        # Убрать из чс
        @dp.callback_query_handler(lambda callback_query: callback_query.data == "blacklist_")
        async def list_admins(callback_query: types.CallbackQuery):
            users_info = await get_user_to_black_list()
            if not users_info:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='admins'))
                await bot.edit_message_text(
                    "Черный список пуст.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)
            else:
                keyboard = InlineKeyboardMarkup()
                for user in users_info:
                    user_id = user['user_id']
                    user_name = user.get('user_name', 'Нет имени')
                    user_number = user.get('user_number', 'Нет номера')
                    button_text = f"👤{user_id}\n👥{user_name}\n📞{user_number}"
                    button = InlineKeyboardButton(button_text, callback_data=f"delete_blacklist_{user_id}")
                    keyboard.add(button)
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='admins'))
                await bot.edit_message_text(
                    "Список пользователей в чс:",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)

        @dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('delete_blacklist_'))
        async def delete_admin(callback_query: types.CallbackQuery):
            user_id = int(callback_query.data.split('_')[2])

            black_list_info = await get_blacklist_info(user_id)
            user_info = await get_user(user_id)

            user_name = 'Нет имени'
            user_number = 'Нет номера'
            keyboard = InlineKeyboardMarkup()

            if black_list_info:
                user_name = black_list_info.get('user_name', user_name)
                user_number = black_list_info.get('user_number', user_number)

            user_name = 'Нет имени'
            user_number = 'Нет номера'

            if user_info:
                user_name = user_info.get('name', user_name)
                user_number = user_info.get('number', user_number)

            if black_list_info:
                keyboard.add(InlineKeyboardButton('🔁 Еще кого то убрать❓', callback_data="blacklist_"))
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='admins'))
                await remove_user_from_black_list(user_id)
                await bot.edit_message_text(
                    f"Пользователь: {user_name}, {user_number}\nID: {user_id} убран из чс.",
                    chat_id=callback_query.from_user.id,
                    message_id=callback_query.message.message_id, reply_markup=keyboard)
            else:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton('🔁 Еще кого то убрать❓', callback_data="blacklist_"))
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='admins'))
                await bot.edit_message_text(
                    f"Пользователь: {user_name}, {user_number}\nID: {user_id} не найден.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)

        @dp.callback_query_handler(lambda callback_query: callback_query.data == "addcategory_")
        async def add_category_handler(callback_query, state: FSMContext):
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Отменить добавление ❓", callback_data='catalogsandproduct'))
            await bot.edit_message_text(
                "Введите название каталога:\nЕсли названий несколько, то будет примерно так:\nНазваниеНазвание\nНе менее 16 символов",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)
            await NewCategory.enter_name.set()

        @dp.message_handler(lambda message: len(message.text) >= 16, state=NewCategory.enter_name)
        async def add_category_name_invalid(message: types.Message):
            await message.reply(
                f'Слишком длинное название.\nСократите название до 16 символов')

        @dp.message_handler(state=NewCategory.enter_name)
        async def add_category_name(message: types.Message, state: FSMContext):
            existing_category = await get_categories_from_db()
            get_categories = [name.get('name', 'Нет имени') for name in existing_category]
            category_name = format_category_name(message.text)
            clean_category_name = re.sub(r'[^a-zA-Zа-яА-Я0-9\s]', '', category_name)
            existing_category = await get_catalog_by_name(category_name)
            if existing_category:
                i = 1
                new_name = f"{clean_category_name}{i}"
                while await get_catalog_by_name(new_name):
                    i += 1
                    new_name = f"{clean_category_name}{i}"
                category_name = new_name

            keyboard = InlineKeyboardMarkup()

            if not clean_category_name:
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='catalogsandproduct'))
                await message.reply(
                    "Введенное название каталога не содержит допустимых символов.\nПожалуйста, используйте только буквы, цифры, избегайте пробелов",
                    reply_markup=keyboard)

                return

            if not category_name:
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='catalogsandproduct'))
                await message.reply("Название категории не может быть пустым. Попробуйте снова.", reply_markup=keyboard)
                return

            if category_name in get_categories:
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='catalogsandproduct'))
                await message.reply("Категория с таким именем уже существует. Пожалуйста, выберите другое имя.",
                                    reply_markup=keyboard)
                return

            await add_category(category_name)
            keyboard.add(InlineKeyboardButton("🔁 Добавить еще", callback_data='addcategory_'))
            keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='catalogsandproduct'))
            await message.reply(f"Категория {category_name} добавлена.", reply_markup=keyboard)
            await state.finish()

        def format_category_name(category_name):
            formatted_words = [word.capitalize() for word in category_name.split()]
            formatted_category_name = ''.join(formatted_words)

            return formatted_category_name

        @dp.callback_query_handler(lambda c: c.data == "deletecategory_")
        async def delete_category_handler(callback_query: types.CallbackQuery):
            categories = await get_categories_from_db()

            if categories:
                keyboard = InlineKeyboardMarkup()
                for category in categories:
                    category_name = category.get('name', 'Нет имени')
                    button = InlineKeyboardButton(category_name,
                                                  callback_data=f"confirm_delete_category_{category_name}")
                    keyboard.add(button)
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data="catalogsandproduct"))
                await bot.edit_message_text(
                    "Выберите категорию для удаления:",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)
            else:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="catalogsandproduct"))
                await bot.edit_message_text(
                    "Нет доступных категорий для удаления.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=await get_admin_inline_keyboard())

        @dp.callback_query_handler(lambda c: c.data.startswith("confirm_delete_category_"))
        async def confirm_delete_category(callback_query: types.CallbackQuery):
            category_name = callback_query.data.split("_")[3]
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("Да", callback_data=f"delete_category_{category_name}"),
                InlineKeyboardButton("Нет", callback_data="catalogsandproduct")
            )
            await bot.edit_message_text(
                f"Вы уверены, что хотите удалить категорию '{category_name}'?",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard
            )

        @dp.callback_query_handler(lambda c: c.data.startswith("delete_category_"))
        async def delete_category(callback_query: types.CallbackQuery):
            category_name = callback_query.data.split("_")[2]
            removed = await remove_category_from_db(category_name)
            if removed:
                await bot.edit_message_text(
                    f"Категория {category_name} удалена.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=await get_admin_inline_keyboard()
                )
            else:
                await bot.edit_message_text(
                    f"Ошибка при удалении категории {category_name}.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=await get_admin_inline_keyboard()
                )

        def format_product_name(product_name):
            formatted_words = [word.capitalize() for word in product_name.split()]
            formatted_product_name = ''.join(formatted_words)
            clean_product_name = re.sub(r'[^a-zA-Zа-яА-Я0-9\s]', '', formatted_product_name)
            return clean_product_name

        @dp.callback_query_handler(lambda c: c.data.startswith('addproduct_'), state='*')
        async def add_product(callback_query: types.CallbackQuery):
            keyboards_get_catalog = await get_addproduct_keyboard()
            cancel_button = InlineKeyboardButton("🔙 Отмена", callback_data="catalogsandproduct")
            keyboards_get_catalog.add(cancel_button)
            await bot.edit_message_text(
                'Выберите категорию, в который нужно добавить товар:',
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboards_get_catalog)
            await ProductForm.add_choice.set()

        @dp.callback_query_handler(lambda c: c.data.startswith('catalog_'), state=ProductForm.add_choice)
        async def catalog_chosen(callback_query: types.CallbackQuery, state: FSMContext):
            catalog_name = callback_query.data.split('_')[1]
            await state.update_data(catalog_name=catalog_name)
            keyboard = InlineKeyboardMarkup()
            cancel_button = InlineKeyboardButton("🔙 Отмена", callback_data="catalogsandproduct")
            keyboard.add(cancel_button)
            await ProductForm.add_name.set()
            await callback_query.message.answer(f"Вы выбрали категорию {catalog_name}")
            await callback_query.message.answer(
                "Введите название товара (если название из 2 слов, то будет НазваниеНазвание)\nНе более 18 символов",
                reply_markup=keyboard)

        @dp.message_handler(lambda message: len(message.text) >= 18, state=ProductForm.add_name)
        async def add_product_name_invalid(message: types.Message):
            await message.reply(
                f'Слишком длинное название.\nСократите название до 18 символов')

        @dp.message_handler(state=ProductForm.add_name)
        async def add_product_name(message: types.Message, state: FSMContext):
            product_name = format_product_name(message.text)
            product = await get_product_by_name(product_name)
            keyboard = InlineKeyboardMarkup()
            cancel_button = InlineKeyboardButton("🔙 Отмена", callback_data="catalogsandproduct")
            keyboard.add(cancel_button)
            if product:
                i = 1
                new_name = f"{product_name}{i}"
                while await get_product_by_name(new_name):
                    i += 1
                    new_name = f"{product_name}{i}"
                product_name = new_name
            await state.update_data(product_name=product_name)
            await ProductForm.add_name_description.set()
            await message.reply('Добавьте описание для названия (количество шт, или сколько мл/гр/кг/л):',
                                reply_markup=keyboard)

        @dp.message_handler(state=ProductForm.add_name_description)
        async def add_product_name_discription(message: types.Message, state: FSMContext):
            keyboard = InlineKeyboardMarkup()
            cancel_button = InlineKeyboardButton("🔙 Отмена", callback_data="catalogsandproduct")
            keyboard.add(cancel_button)
            name_description = message.text
            await state.update_data(name_description=name_description)
            await ProductForm.add_price.set()
            await message.reply('Введите цену товара:', reply_markup=keyboard)

        @dp.message_handler(lambda message: not message.text.replace(".", "", 1).isdigit(), state=ProductForm.add_price)
        async def add_product_invalid_price(message: types.Message):
            await message.reply('Пожалуйста, введите цену товара в числовом формате. Например, 10.99')

        @dp.message_handler(lambda message: message.text.replace(".", "", 1).isdigit(), state=ProductForm.add_price)
        async def add_product_price(message: types.Message, state: FSMContext):
            keyboard = InlineKeyboardMarkup()
            cancel_button = InlineKeyboardButton("🔙 Отмена", callback_data="catalogsandproduct")
            keyboard.add(cancel_button)
            product_price = float(message.text)
            await state.update_data(product_price=product_price)
            await ProductForm.add_quantity.set()
            await message.reply('Введите количество товара:', reply_markup=keyboard)

        @dp.message_handler(lambda message: not message.text.isdigit(), state=ProductForm.add_quantity)
        async def add_product_invalid_quantity(message: types.Message):
            await message.reply('Пожалуйста, введите количество товара в числовом формате. Например, 10')

        @dp.message_handler(lambda message: message.text.isdigit(), state=ProductForm.add_quantity)
        async def add_product_quantity(message: types.Message, state: FSMContext):
            product_quantity = int(message.text)
            await state.update_data(product_quantity=product_quantity)
            await ProductForm.add_photo.set()
            await message.reply('Загрузите изображение товара (отправьте изображение в чат).')

        @dp.message_handler(content_types=types.ContentType.PHOTO, state=ProductForm.add_photo)
        async def add_product_photo(message: types.Message, state: FSMContext):

            user_id = message.from_user.id

            data = await state.get_data()
            product_name = data['product_name']
            name_description = data['name_description']
            product_price = data['product_price']
            product_quantity = data['product_quantity']
            catalog_name = data['catalog_name']
            image_id = await save_image(message.photo)
            product_info = {
                "_id": ObjectId(),
                "product_name": product_name,
                "name_description": name_description,
                "product_price": product_price,
                "quantity": product_quantity,
                "image_id": image_id
            }
            keyboard = InlineKeyboardMarkup()
            success = await add_product_to_category(catalog_name, product_info)
            if success:
                keyboard.add(InlineKeyboardButton("🔁 Добавить ещё", callback_data="addproduct_"))
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='catalogsandproduct'))
                await message.answer("Товар добавлен", reply_markup=keyboard)
                await state.finish()
            else:
                keyboard.add(InlineKeyboardButton("🔁 Попробовать снова", callback_data="addproduct_"))
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='catalogsandproduct'))
                await message.answer("Не удалось добавить продукт в базу данных.", reply_markup=keyboard)

        async def get_categories_delete():
            catalogs = await get_categories_from_db()
            categories_data = []

            for category in catalogs:
                category_name = category.get('name', 'Нет имени')
                categories_data.append(category_name)

            return categories_data

        @dp.callback_query_handler(lambda c: c.data.startswith("deleteproduct_"))
        async def delete_product(callback_query: types.CallbackQuery, state: FSMContext):
            categories = await get_categories_from_db()

            if not categories:
                await bot.edit_message_text(
                    "В базе данных нет категорий.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=await get_admin_inline_keyboard())
                await state.finish()
                return

            keyboard = InlineKeyboardMarkup()
            for category in categories:
                category_name = category['name']
                keyboard.add(InlineKeyboardButton(category_name, callback_data=f"choosecategory_{category_name}"))
            keyboard.add(InlineKeyboardButton("🔙 Передумали ?", callback_data='catalogsandproduct'))
            await state.update_data(action="deleteproduct")
            await DeleteProduct.select_category.set()
            await bot.edit_message_text(
                "Выберите категорию для удаления товара:",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)

        @dp.callback_query_handler(lambda c: c.data.startswith("choosecategory_"), state=DeleteProduct.select_category)
        async def choose_category(callback_query: types.CallbackQuery, state: FSMContext):
            selected_category = callback_query.data.split('_')[1]
            products = await get_products_in_category(selected_category)

            if not products:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔁 Выберите другую ?", callback_data="deleteproduct_"))
                keyboard.add(InlineKeyboardButton("🔙 Отмена", callback_data='catalogsandproduct'))
                await bot.edit_message_text(
                    "В этой категории нет товаров.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)
                await state.finish()
                return

            keyboard = InlineKeyboardMarkup()
            for product in products:
                product_name = product['product_name']
                keyboard.add(InlineKeyboardButton(product_name,
                                                  callback_data=f"confirmdelete_{selected_category}_{product_name}"))
            keyboard.add(InlineKeyboardButton("🔙 Передумали ?", callback_data='catalogsandproduct'))
            await state.update_data(selected_category=selected_category)
            await DeleteProduct.select_product.set()
            await bot.edit_message_text(
                "Выберите товар для удаления:",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)

        @dp.callback_query_handler(lambda c: c.data.startswith("confirmdelete_"), state=DeleteProduct.select_product)
        async def confirm_delete_product(callback_query: types.CallbackQuery, state: FSMContext):
            state_data = await state.get_data()
            selected_category = state_data.get('selected_category')

            data_parts = callback_query.data.split("_")
            product_name = data_parts[2]
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("Да", callback_data=f"deleteproduct1_{selected_category}_{product_name}"),
                InlineKeyboardButton("Нет", callback_data="catalogsandproduct")
            )
            await bot.edit_message_text(
                f"Вы уверены, что хотите удалить товар '{product_name}' из категории '{selected_category}'?",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard
            )

        @dp.callback_query_handler(lambda c: c.data.startswith("deleteproduct1_"), state=DeleteProduct.select_product)
        async def delete_product_confirmed(callback_query: types.CallbackQuery, state: FSMContext):
            state_data = await state.get_data()
            selected_category = state_data.get('selected_category')

            data_parts = callback_query.data.split("_")
            category_name = data_parts[1]
            product_name = data_parts[2]
            result = await remove_product_from_db(category_name, product_name)
            keyboard = InlineKeyboardMarkup()

            if result:
                keyboard.add(InlineKeyboardButton("🔁 Удалить еще?", callback_data="deleteproduct_"))
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='catalogsandproduct'))
                await bot.edit_message_text(
                    "Товар удален",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)
            else:
                keyboard.add(InlineKeyboardButton("🔁 Попробуйте снова?", callback_data="deleteproduct_"))
                keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='catalogsandproduct'))
                await bot.edit_message_text(
                    "Произошла ошибка при удалении товара. Возможно, товар не найден.",
                    callback_query.from_user.id, callback_query.message.message_id,
                    reply_markup=keyboard)
            await state.finish()

        @dp.callback_query_handler(lambda c: c.data == "stats")
        async def send_daily_stats(callback_query: CallbackQuery):
            keyboard = InlineKeyboardMarkup()
            daily_stats = InlineKeyboardButton("День", callback_data="daily_stats")
            weekly_stats = InlineKeyboardButton("Неделя", callback_data="weekly_stats")
            monthly_stats = InlineKeyboardButton("Месяц", callback_data="monthly_stats")
            keyboard.add(daily_stats, weekly_stats, monthly_stats)
            keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='admins'))
            await bot.edit_message_text(
                'Статистика:',
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)

        @dp.callback_query_handler(lambda c: c.data == "daily_stats")
        async def send_daily_stats(callback_query: CallbackQuery):
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="stats"))
            today = datetime.utcnow()
            stats = await get_daily_stats(today)
            await bot.edit_message_text(
                f"Статистика за день:\nНовых пользователей: {stats}",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)

        @dp.callback_query_handler(lambda c: c.data == "weekly_stats")
        async def send_weekly_stats(callback_query: CallbackQuery):
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="stats"))
            today = datetime.utcnow()
            week_ago = today - timedelta(days=7)
            stats = await get_stats_for_period(week_ago, today)
            await bot.edit_message_text(
                f"Статистика за неделю:\n{stats}",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)

        @dp.callback_query_handler(lambda c: c.data == "monthly_stats")
        async def send_monthly_stats(callback_query: CallbackQuery):
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="stats"))
            today = datetime.utcnow()
            month_ago = today - timedelta(days=30)

            stats = await get_stats_for_period(month_ago, today)
            await bot.edit_message_text(
                f"Статистика за месяц:\n{stats}",
                callback_query.from_user.id, callback_query.message.message_id,
                reply_markup=keyboard)

        # @dp.callback_query_handler(lambda c: c.data == 'select_user')
        # async def select_user(callback_query: types.CallbackQuery):
        #
        #     users = await get_users_from_db()
        #
        #     keyboard = types.InlineKeyboardMarkup()
        #     for user in users:
        #         user_id = user['user_id']
        #         user_name = user.get('name', 'Без имени')
        #         button_text = f"ID: {user_id}, Name: {user_name}"
        #         keyboard.insert(types.InlineKeyboardButton(text=button_text, callback_data=f"user_selected_{user_id}"))
        #
        #     await callback_query.message.answer("Select user", reply_markup=keyboard)
        #
        # @dp.callback_query_handler(lambda c: c.data.startswith('user_selected_'))
        # async def user_selected(callback_query: types.CallbackQuery, state: FSMContext):
        #
        #     user_id = int(callback_query.data.split('_')[2])
        #     user = await get_user(user_id)
        #
        #     await state.update_data(selected_user=user)
        #
        #
        # @dp.callback_query_handler(lambda c: c.data.startswith('user_page_'))
        # async def show_user_page(callback_query: types.CallbackQuery):
        #     user_id = int(callback_query.data.split('_')[2])
        #
        #     user = await get_user(user_id)
        #     user_info = await get_user_info(user_id)
        #
        #     await callback_query.message.answer(text=user_info)
        #
        #     keyboard = types.InlineKeyboardMarkup()
        #     keyboard.add(
        #         types.InlineKeyboardButton(text="Посмотреть заказы", callback_data=f"orders:{user_id}")
        #     )
        #     keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="select_user"))
        #
        #     await callback_query.message.answer("Действия:", reply_markup=keyboard)
        #
        # @dp.callback_query_handler(lambda c: c.data.startswith('orders:'))
        # async def show_user_orders(callback_query: types.CallbackQuery):
        #     user_id = callback_query.data.split(':')[1]
        #
        #     orders = await get_user_orders(user_id)
        #
        #     await callback_query.message.answer(text=orders)



    else:
        user_info = await get_user(user_id)

        if user_info:
            user_name = user_info.get('name', "Обновите")
            user_number = user_info.get('number', "Обновите")
            response = f"🆔Ваш ID: {user_info['user_id']}\n"
            response += f"🛂Ваше имя: {user_name}\n"
            response += f"☎️Ваш номер: {user_number}"

            personal_change = InlineKeyboardMarkup(row_width=1)
            personal_change.add(
                InlineKeyboardButton("📝 Изменить имя ⬅", callback_data="change_name_"),
            )
            personal_change.add(
                InlineKeyboardButton("☎️ Изменить номер ⬅", callback_data="change_number_"),
            )
            personal_change.add(InlineKeyboardButton("🔙 Назад", callback_data='назад'))

            try:
                await bot.edit_message_text(
                    response, user_id, callback_query.message.message_id,
                    reply_markup=personal_change
                )
            except MessageToEditNotFound:
                await bot.send_message(user_id, response, reply_markup=personal_change)

            async def start_user_input(callback_query, message_text, state):
                user_id = callback_query.from_user.id
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("↩️ Отмена", callback_data=f"canceladd{state}"))

                try:
                    await bot.edit_message_text(message_text, user_id, callback_query.message.message_id,
                                                reply_markup=keyboard)
                except MessageToEditNotFound:
                    await bot.send_message(user_id, message_text, reply_markup=keyboard)

                await state.set()

            @dp.callback_query_handler(lambda c: c.data == "change_name_")
            async def change_name(callback_query: types.CallbackQuery):
                await start_user_input(callback_query, "✍ Введите новое имя:", UpdateUserData.change_name)

            @dp.callback_query_handler(lambda c: c.data == "change_number_")
            async def change_number(callback_query: types.CallbackQuery):
                await start_user_input(callback_query, "✍ Введите новый номер:", UpdateUserData.change_number)

            @dp.message_handler(state=UpdateUserData.change_name)
            async def set_new_name(message: types.Message, state: FSMContext):
                new_name = message.text.strip()
                back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="назад")
                back_keyboard = InlineKeyboardMarkup().add(back_button)
                if not new_name:
                    await message.answer("❌ Некорректное имя. Пожалуйста, введите корректное имя.")
                    return

                user_id = message.from_user.id
                updated = await update_user_name(user_id, new_name)

                if updated:
                    await bot.delete_message(message.chat.id, message.message_id - 1)

                    await message.answer(text="✅ Имя обновлено.", reply_markup=back_keyboard)
                else:
                    await message.answer(text="❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь.",
                                         reply_markup=back_keyboard)

                await state.finish()

            @dp.message_handler(state=UpdateUserData.change_number)
            async def set_new_number(message: types.Message, state: FSMContext):
                new_number = re.sub(r'[^0-9]', '', message.text)  # Замена букв и пробелов на пустые строки
                user_id = message.from_user.id
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("↩️ Отмена", callback_data="show_profile"))

                if not re.match(r'^\d{9,}$', new_number):
                    await message.answer(text="❌ Некорректный номер телефона. Пожалуйста, введите корректный номер:",
                                         reply_markup=keyboard)
                    return

                updated = await update_user_number(user_id, new_number)

                if updated:
                    await bot.delete_message(message.chat.id, message.message_id - 1)
                    show_profile = InlineKeyboardMarkup(InlineKeyboardButton("Назад", callback_data="show_profile"))
                    await message.answer("✅ Номер телефона обновлен.", reply_markup=show_profile)
                else:
                    await message.answer("❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь.",
                                         reply_markup=menu_keyboard)

                await state.finish()

        else:
            personal_kb = InlineKeyboardMarkup(row_width=2)
            personal_kb.add(
                InlineKeyboardButton("📝 Регистрация ℹ", callback_data="register"),
            )
            personal_kb.add(
                InlineKeyboardButton("🔙 Вернуться назад", callback_data="назад"),
            )
            await bot.edit_message_text("❗ Зарегистрируйтесь ❗", user_id, callback_query.message.message_id,
                                        reply_markup=personal_kb)

            @dp.callback_query_handler(lambda callback_query: callback_query.data == "register")
            async def register_start(callback_query: types.CallbackQuery):
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("Отмена", callback_data="canceladdname1"))
                await bot.edit_message_text("✍ Введите имя:", user_id, callback_query.message.message_id,
                                            reply_markup=keyboard)
                await AddPerson.add_name.set()

            @dp.message_handler(lambda message: message.text and not re.match(r'^[0-9\+\-\(\)]+$', message.text),
                                state=AddPerson.add_name)
            async def register_name(message: types.Message, state: FSMContext):
                async with state.proxy() as data:
                    data['name'] = message.text
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("Отмена", callback_data="canceladdnumber1"))
                await bot.edit_message_text(
                    "✅ Имя сохранено. Теперь введите номер телефона:\nПример:\n0999-123-456\n0999123456", user_id,
                    callback_query.message.message_id,
                    reply_markup=keyboard)
                await AddPerson.add_number.set()

            @dp.message_handler(lambda message: not ''.join(filter(str.isdigit, message.text)),
                                state=AddPerson.add_number)
            async def handle_non_digit_input(message: types.Message):
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton('Отмена', callback_data='canceladdnewnumber'))
                await message.answer("❌ Некорректный ввод. Пожалуйста, введите только цифры.", reply_markup=keyboard)
                await bot.edit_message_text(
                    "❌ Некорректный ввод.\nПожалуйста, введите только цифры.\nПример:\n0999123456",
                    message.from_user.id,
                    message.message_id,
                    reply_markup=keyboard
                )

            @dp.message_handler(lambda message: re.match(r'^[0-9\(\)]+$', ''.join(filter(str.isdigit, message.text))),
                                state=AddPerson.add_number)
            async def register_number(message: types.Message, state: FSMContext):
                async with state.proxy() as data:
                    data['number'] = ''.join(filter(str.isdigit, message.text))
                text = "❌ Некорректный ввод.\nПожалуйста, введите только цифры.\nПример:\n0999123456\nДолжно быть более 9 цифр"
                if len(data['number']) < 9:
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(InlineKeyboardButton('Отмена', callback_data='canceladdnewnumber'))
                    await message.answer(text, reply_markup=keyboard)
                    return

                user_id = message.from_user.id
                name = data['name']
                number = data['number']
                await add_user(user_id, name, number)

                await state.finish()
                await message.answer(
                    "✅ Регистрация завершена. Ваши данные обновлены!",
                    reply_markup=menu_keyboard)

            @dp.callback_query_handler(lambda c: c.data == 'canceladdname1', state=AddPerson.add_name)
            async def canceldelete_product(callback_query: types.CallbackQuery, state: FSMContext):
                await bot.edit_message_text(
                    'Действие отменено', user_id,
                    callback_query.message.message_id,
                    reply_markup=menu_keyboard)
                await state.finish()

            @dp.callback_query_handler(lambda c: c.data == 'canceladdnumber1', state=AddPerson.add_number)
            async def canceldelete_product(callback_query: types.CallbackQuery, state: FSMContext):
                await bot.edit_message_text(
                    'Действие отменено', user_id,
                    callback_query.message.message_id,
                    reply_markup=menu_keyboard)
                await state.finish()
