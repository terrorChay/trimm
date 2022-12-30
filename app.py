import streamlit as st
import utils as utils
from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
from io import BytesIO

regions = {
    'Астрахань' : 'https://prodoctorov.ru/astrahan/lpu',
    'Сочи'      : 'https://prodoctorov.ru/sochi/lpu',
    'Тюмень'    : 'https://prodoctorov.ru/tyumen/lpu',
    'Воронеж'   : 'https://prodoctorov.ru/voronezh/lpu',
}

@st.experimental_memo
def scrape(address):
    # Define things to find
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

    # Output dataframe to fil
    df = pd.DataFrame(columns=['Название', 'Тип', 'Кол-во врачей', 'Адрес', 'Телефон', 'Открыто до', 'Представлено цен', 'Отзывов'])

    page_num = 1
    response = '200'
    while response == '200':
        url = f"{address}/?page={page_num}"
        page = requests.get(url)
        response = str(page.status_code)
        if response == '200':
            page_num += 1
            soup = BeautifulSoup(page.text, "html.parser")
            # Iterate over clinic cards
            allLPU = soup.findAll('div', class_='b-card__row')
            for item in allLPU:
                item_data = []
                for key, attrs in target_attrs.items():
                    data_unit = item.find(*attrs)
                    if data_unit is not None:
                        raw_text = data_unit.text.strip("""\n               """)
                        if key == 'Кол-во врачей' or key == 'Отзывы':
                            raw_text = re.sub(r"\D", "", raw_text)
                        item_data.append(raw_text)
                    else:
                        item_data.append(data_unit)
                df.loc[len(df)] = item_data
    st.success(f'Проанализировано {page_num-1} страниц! Страница {page_num} вернула ошибку {response}.')
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
    st.header('prodoctorov.ru ЛПУ парсер')
    with st.form('parser'):
        region = st.selectbox('Выберите регион', ['Астрахань', 'Сочи', 'Тюмень', 'Воронеж'])
        address = regions[region]
        submit = st.form_submit_button('Поехали')
    if submit:
        df = scrape(address)
        st.dataframe(df)
        st.download_button('💾 Excel', data=convert_df(df, True), file_name=f"{region}.xlsx")

if __name__ == "__main__":
    utils.page_config(layout='centered', title='matyush.in')
    utils.remove_footer()
    main()