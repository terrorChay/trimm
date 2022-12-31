import streamlit as st
import utils as utils
from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
from io import BytesIO

regions = {
    'Астрахань' : 'https://prodoctorov.ru/astrahan/',
    'Сочи'      : 'https://prodoctorov.ru/sochi/',
    'Тюмень'    : 'https://prodoctorov.ru/tyumen/',
    'Воронеж'   : 'https://prodoctorov.ru/voronezh/',
}

@st.experimental_memo
def scrape(address, find_lpu, page_limit):
    # Define things to find
    if find_lpu:
        target_attrs = {
            'Название'      : ('span', {"data-qa": "lpu_card_heading_lpu_name"}),
            'Тип'           : ('div', {"data-qa": "lpu_card_subheading_lputype_name"}),
            'Кол-во врачей' : ('div', {"data-qa": "lpu_card_subheading_doctors_count"}),
            'Адрес'         : ('span', {"data-qa": "lpu_card_btn_addr_text"}),
            'Телефон'       : ('span', {"data-qa": "lpu_card_btn_phone_text"}),
            'Открыто до'    : ('span', {"data-qa": "lpu_card_btn_schedule_text"}),
            'Цены'          : ('span', {"data-qa": "lpu_card_btn_prices_num"}),
            'Отзывы'        : ('span', {"data-qa": "lpu_card_stars_text"}),
        }
    else:
        target_attrs = {
            'ФИО'               : ('span', {"class": "b-doctor-card__name-surname"}),
            'Специальность'     : ('div', {"class": "b-doctor-card__spec"}),
            'Стаж'              : ('div', {"class": "b-doctor-card__experience-years"}),
            'Категория'         : ('div', {"class": "b-doctor-card__category"}),
            'Отзывов'           : ('a', {"class": "ui-text ui-text_body-2 b-link b-link_prg b-link_color_grey b-link_underline"}),
            'Клиника'           : ('span', {"class": "b-select__trigger-main-text"}),
            'Адрес клиники'     : ('span', {"class": "b-select__trigger-adit-text"}),
        }

    # Output dataframe to fil
    df = pd.DataFrame(columns=target_attrs.keys())

    page_num = 1
    response = '200'
    while response == '200' and page_num-1 != page_limit:
        url = f"{address}/?page={page_num}"
        page = requests.get(url)
        response = str(page.status_code)
        if response == '200':
            page_num += 1
            soup = BeautifulSoup(page.text, "html.parser")
            # Iterate over
            if find_lpu:
                all = soup.findAll('div', class_='b-card__row')
            else:
                all = soup.findAll('div', class_='b-doctor-card')
            for item in all:
                item_data = []
                for key, attrs in target_attrs.items():
                    data_unit = item.find(*attrs)
                    if data_unit is not None:
                        raw_text = data_unit.text.strip("""\n               """)
                        if key == 'Кол-во врачей' or key == 'Отзывы':
                            raw_text = re.sub(r"\D", "", raw_text)
                        elif key == 'Специальность':
                            raw_text = ', '.join(list(map(lambda x: x.strip() , raw_text.split(','))))
                        item_data.append(raw_text)
                    else:
                        item_data.append(data_unit)
                df.loc[len(df)] = item_data
    st.success(f'Проанализировано {page_num-1} страниц! Страница {page_num} вернула код {response}.')
    return df

@st.experimental_memo
def convert_df(df: pd.DataFrame, to_excel=False):
    if to_excel:
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='ilya-matyushin')
        workbook = writer.book
        worksheet = writer.sheets['ilya-matyushin']
        format1 = workbook.add_format({'num_format': '0.00'}) 
        worksheet.set_column('A:A', None, format1)  
        workbook.close()
        processed_data = output.getvalue()
    else:
        processed_data = df.to_csv().encode('utf-8')
    return processed_data

def main():
    st.subheader('ilya@matyush.in')
    with st.form('parser'):
        region = st.selectbox('Где ищем?', ['Астрахань', 'Сочи', 'Тюмень', 'Воронеж'])
        to_find = st.selectbox('Что ищем?', ['ЛПУ', 'Врачи'])
        page_limit = st.select_slider('Максимум страниц', options=['Нет']+list(range(1,21)))
        address = regions[region]
        submit = st.form_submit_button('Поехали')
    if submit:
        if to_find == 'ЛПУ':
            df = scrape(address+'lpu', True, page_limit)
        else:
            df = scrape(address+'vrach', False, page_limit)
        st.dataframe(df)
        st.download_button('💾 Excel', data=convert_df(df, True), file_name=f"{region}.xlsx")

if __name__ == "__main__":
    utils.page_config(layout='centered', title='matyush.in')
    utils.remove_footer()
    main()