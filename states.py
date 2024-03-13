from aiogram.dispatcher.filters.state import State, StatesGroup


class ProductForm(StatesGroup):
    choose_category = State()
    add_choice = State()
    add_name = State()
    add_name_description = State()
    add_price = State()
    add_quantity = State()
    add_description = State()
    add_link = State()
    add_photo = State()


class EditProduct(StatesGroup):
    select_product = State()
    enter_new_data = State()
    select_category = State()
    select_attribute = State()


class EditCatalogName(StatesGroup):
    enter_new_name = State()
    waiting_for_catalog_selection = State()


class AddMessengerState(StatesGroup):
    waiting_for_contact = State()
    waiting_for_messenger_name = State()


class DeliveryState(StatesGroup):
    waiting_for_address = State()


class AddProductQuantity(StatesGroup):
    add_quantity = State()
    add_product_confirmation = State()


class UpdateContact(StatesGroup):
    waiting_for_contact = State()


class AddContactState(StatesGroup):
    waiting_for_contact = State()
    waiting_for_messanger = State()


class PickupAddressState(StatesGroup):
    waiting_for_address = State()


class UpdateAddressState(StatesGroup):
    waiting_for_new_address = State()


class DeleteAddressState(StatesGroup):
    waiting_for_confirmation = State()


class RemoveContactState(StatesGroup):
    waiting_for_contact = State()
    waiting_for_confirmation = State()


class Broadcast(StatesGroup):
    waiting_text = State()


class NewCategory(StatesGroup):
    enter_name = State()


class UserForm(StatesGroup):
    add_admin = State()
    add_admin_name = State()
    remove_admin = State()
    black_list = State()
    del_black_list = State()


class AddPerson(StatesGroup):
    add_name = State()
    add_number = State()
    change_name = State()
    change_number = State()


class AddNewPerson(StatesGroup):
    add_name = State()
    add_number = State()
    change_name = State()
    change_number = State()


class UpdateUserData(StatesGroup):
    change_name = State()
    change_number = State()


class DeleteProduct(StatesGroup):
    select_category = State()
    select_product = State()
    confirm_delete = State()


class SetDeliveryState(StatesGroup):
    waiting_for_delivery = State()
    waiting_for_address = State()
    waiting_for_contact_data = State()
