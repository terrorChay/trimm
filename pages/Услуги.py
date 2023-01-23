import streamlit as st
import utils as utils
from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
from io import BytesIO
from geopy.geocoders import Nominatim
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)
from streamlit import session_state as session

@st.experimental_memo
def scrape(address, to_find):
    # Define things to find
    target_attrs = {
        'Название'      : ('span', {"data-qa": "lpu_card_heading_lpu_name"}),
        'Адрес'         : ('span', {"data-qa": "lpu_card_btn_addr_text"}),
        'Телефон'       : ('span', {"data-qa": "lpu_card_btn_phone_text"}),
        'Открыто до'    : ('span', {"data-qa": "lpu_card_btn_schedule_text"}),
        'Кнопка'        : ('span', {"class":"ui-text ui-text_button"})
    }

    # Output dataframe to fil
    df = pd.DataFrame(columns=target_attrs.keys())
    supposed_page = 0
    response = '200'
    while response == '200':
        supposed_page += 1
        url = f"{address}diagnostika/{to_find}/?page={supposed_page}"
        page = requests.get(url)
        response = str(page.status_code)
        if response == '200':
            soup = BeautifulSoup(page.text, "html.parser")
            curpage_items = soup.findAll('span', class_='b-pagination-vuetify-imitation__item b-pagination-vuetify-imitation__item_current')
            # Get actual page
            if len(curpage_items) == 0:
                actual_page = 1
            else:
                actual_page = int(curpage_items[0].text)

            # Iterate over cards if supposed and actual page matches
            if supposed_page == actual_page:
                all = soup.findAll('div', class_='b-card__row')
                for item in all:
                    item_data = []
                    for key, attrs in target_attrs.items():
                        data_unit = item.find(*attrs)
                        if data_unit is not None:
                            raw_text = data_unit.text.strip("""\n               """)
                            item_data.append(raw_text)
                        else:
                            item_data.append(data_unit)
                    df.loc[len(df)] = item_data
            else:
                response = f'Supposed page {supposed_page} does not match actual page {actual_page}'
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

# Apply filters and return filtered dataset
def filter_dataframe(df: pd.DataFrame, cols_to_ignore=[]) -> pd.DataFrame:
    df = df.copy()
    # Try to convert datetimes into a standard format (datetime, no timezone)
    for col in df.columns:
        if is_object_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

    modification_container = st.container()
    with modification_container:
        cols = [col for col in df.columns if col not in cols_to_ignore]
        to_filter_columns = st.multiselect("Параметры фильтрации", cols)
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            left.write("└")
            if is_numeric_dtype(df[column]):
                _min = float(df[column].min())
                _max = float(df[column].max())
                step = (_max - _min) / 100
                user_num_input = right.slider(
                    f" {column}",
                    min_value=_min,
                    max_value=_max,
                    value=(_min, _max),
                    step=step,
                )
                df = df[df[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(df[column]):
                user_date_input = right.date_input(
                    f" {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
            elif (is_categorical_dtype(df[column]) or df[column].nunique() < 10 or df[column].map(len).max() < 255) and ('Название' not in df[column].name):
                options = df[column].unique()
                user_cat_input = right.multiselect(
                    f"{column}",
                    options,
                )
                if user_cat_input:
                    _cat_input = user_cat_input
                    df = df[df[column].isin(_cat_input)]
            else:
                user_text_input = right.text_input(
                    f"{column}",
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input, na=False, flags=re.IGNORECASE)]
    # Try to convert datetimes into displayable date formats
    for col in df.columns:
        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%d-%m-%Y')
    return df

def main():
    regions = {
        'Астрахань' : 'https://prodoctorov.ru/astrahan/',
        'Сочи'      : 'https://prodoctorov.ru/sochi/',
        'Тюмень'    : 'https://prodoctorov.ru/tyumen/',
        'Воронеж'   : 'https://prodoctorov.ru/voronezh/',
    }

    services = {
        'МРТ'       : 'mrt',
        'КТ'        : 'kt',
        'Рентген'   : 'rentgen',
    }
    geolocator = Nominatim(user_agent='Tester')
    st.subheader('ilya@matyush.in')
    with st.form('parser'):
        region = st.selectbox('Где ищем?', regions.keys())
        to_find = st.multiselect('Что ищем?', services.keys())
        address = regions[region]
        submit = st.form_submit_button('Найти')
    if submit:
        dfs = []
        for service in to_find:
            dfs.append(scrape(regions[region], services[service]))

        df_merged = pd.DataFrame()
        for idx, item in enumerate(dfs):
            if idx == 0:
                df_merged = item
            else:
                df_merged = df_merged.merge(item, on='Название', how='inner', suffixes=('', '_remove'))
        df_merged.drop([i for i in df_merged.columns if 'remove' in i], axis=1, inplace=True)
        
        st.success(f'В регионе  {region} найдено {df_merged.shape[0]} клиник, в которых можно сделать {", ".join(to_find)}')
        session['df'] = df_merged

    if 'df' not in session:
        session['df'] = None
    df = session['df']
    if type(df) == pd.DataFrame:
        df_filters_applied  = filter_dataframe(df)
        if df_filters_applied.shape[0]:
            st.dataframe(df_filters_applied)
            st.download_button('💾 Excel', data=convert_df(df_filters_applied, True), file_name=f"{region}.xlsx")
    else:
        st.warning('Выполните поиск')

if __name__ == "__main__":
    utils.page_config(layout='centered', title='matyush.in')
    utils.remove_footer()
    main()