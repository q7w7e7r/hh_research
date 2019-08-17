"""
------------------------------------------------------------------------

Title         : hh_research.py
Author        : Alexander Kapitanov
E-mail        : sallador@bk.ru
Lang.         : python
Company       :
Release Date  : 2019/08/14

------------------------------------------------------------------------

Description   :
    HeadHunter (hh.ru) research script.

    1. Get data from hh.ru by user request (i.e. 'Machine learning')
    2. Collect all vacancies.
    3. Parse JSON and get useful values: salary, experience, name,
    skills, employer name etc.
    4. Calculate some statistics: average salary, median, std, variance

------------------------------------------------------------------------

GNU GENERAL PUBLIC LICENSE
Version 3, 29 June 2007

Copyright (c) 2019 Kapitanov Alexander

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
APPLICABLE LAW. EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT
WARRANTY OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT
NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
FOR A PARTICULAR PURPOSE. THE ENTIRE RISK AS TO THE QUALITY AND
PERFORMANCE OF THE PROGRAM IS WITH YOU. SHOULD THE PROGRAM PROVE
DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY SERVICING, REPAIR OR
OR CORRECTION.

------------------------------------------------------------------------
"""
from concurrent.futures import ThreadPoolExecutor
import os
import re

import pandas as pd
import requests
from tqdm import tqdm


def form_url():
    """
    Create full URL by using input parameters

    Returns
    -------
    string
        Full URL for requests

    """
    hh_url = 'https://api.hh.ru/vacancies?'
    hh_dct = {
        'area': 1,
        'text': 'Machine learning',
        'per_page': 50,
    }
    hh_lst = '&'.join([i + '=' + str(hh_dct[i]).replace(' ', '+') for i in hh_dct])
    return hh_url + hh_lst


HH_URL = form_url()
EX_URL = 'https://api.exchangerate-api.com/v4/latest/RUB'
MAX_WORKERS = int(os.getenv('MAX_WORKERS', 5))

exchange_rates = {}


def update_exchange_rates():
    """
    Parse exchange rate for RUB, USD, EUR and save them to `exchange_rates`
    """
    try:
        print('Try to get rates from URL...')
        resp = requests.get(EX_URL)
        rates = resp.json()['rates']

    except requests.exceptions.SSLError:
        print('Cannot get exchange rate! Try later or change host API')
        exit('Exit from script. Cannot get data from URL!')

    for curr in ['RUB', 'USD', 'EUR']:
        exchange_rates[curr] = rates[curr]

    # Change 'RUB' to 'RUR'
    exchange_rates['RUR'] = exchange_rates.pop('RUB')
    print(f'Get exchange rates: {exchange_rates}')


def get_list_id():
    """
    Check if file with vacancy IDs exists.

    Get ID list and save it to file if doesn't exist.
    Request: GET data from URL by using JSON.

    Returns
    -------
    list
        ID list for vacancies

    """
    fname = 'id_list.dat'
    try:
        with open(fname) as f:
            print('File with IDs exists. Read file...')
            return [el.rstrip() for el in f]
    except IOError:
        print('File with IDs does not exist. Create file...')

        id_lst = []
        nm_pages = requests.api.get(HH_URL).json()['pages']
        for i in range(nm_pages + 1):
            page_url = HH_URL + f'&page={i}'
            page_req = requests.api.get(page_url).json()['items']
            for el in page_req:
                id_lst.append(el['id'])

        with open(fname, 'w') as f:
            for el in id_lst:
                f.write("%s\n" % el)
        return id_lst


def clean_tags(str_html):
    """
    Remove HTML tags from string (text)

    Returns
    -------
    string
        Clean text without tags

    """
    pat = re.compile('<.*?>')
    res = re.sub(pat, '', str_html)
    return res


def get_vacancy(vacancy_id):
    # Vacancy URL
    url = f'https://api.hh.ru/vacancies/{vacancy_id}'
    vacancy = requests.api.get(url).json()

    # Extract salary
    salary = vacancy['salary']

    # Calculate salary:
    # Get salary into {RUB, USD, EUR} with {Gross} parameter and
    # return a new salary in RUB.
    cl_ex = {'from': None, 'to': None}
    if salary:
        # fn_gr = lambda: 0.87 if vsal['gross'] else 1
        def fn_gr():
            return 0.87 if vacancy['salary']['gross'] else 1

        for i in cl_ex:
            if vacancy['salary'][i] is not None:
                cl_ex[i] = int(
                    fn_gr() * salary[i] / exchange_rates[salary['currency']]
                )

    # Create pages tuple
    return (
        vacancy_id,
        vacancy['employer']['name'],
        vacancy['name'],
        salary is not None,
        cl_ex['from'],
        cl_ex['to'],
        vacancy['experience']['name'],
        vacancy['schedule']['name'],
        [el['name'] for el in vacancy['key_skills']],
        clean_tags(vacancy['description']),
    )


def get_vacancies(ids):
    """
    Parse vacancy JSON: get vacancy name, salary, experience etc.

    Parameters
    ----------
    ids: list
        list of vacancies

    Returns
    -------
    list
        List of useful arguments from vacancies

    """
    vacancies = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for vacancy in tqdm(executor.map(get_vacancy, ids), total=len(ids)):
            vacancies.append(vacancy)

    return vacancies


def prepare_df(dct_df):
    # List of columns
    df_cols = ['Id',
               'Employer',
               'Name',
               'Salary',
               'From',
               'To',
               'Experience',
               'Schedule',
               'Keys',
               'Description',
               ]
    # Create pandas dataframe
    df = pd.DataFrame(data=dct_df, columns=df_cols)
    # Print some info from data frame
    print(
        df[df['Salary']][['Employer', 'From', 'To', 'Experience']][0:10]
    )
    # Save to file
    df.to_csv(r'hh_data.csv', index=False)


if __name__ == "__main__":
    print('Run hh.ru analysis...')
    update_exchange_rates()
    id_list = get_list_id()
    print('Collect data from JSON. Create list of vacancies...')
    vac_list = get_vacancies(ids=id_list)
    print('Prepare data frame...')
    prepare_df(vac_list)
    print('Done. Exit()')

# TODO: From / To list function. Average salary. Currency: convert to RUR.
