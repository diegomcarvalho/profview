"""
# My first app
Here's our first attempt at using data to create a table:
"""

from collections import defaultdict
import streamlit as st
import pandas as pd

from calendar_view.core import data
from calendar_view.core.config import CalendarConfig
from calendar_view.config import style
from calendar_view.calendar import Calendar
from calendar_view.core.event import Event
from calendar_view.core.event import EventStyles


from typing import Callable
import os


style.hour_height = 100


def st_init():
    st.set_page_config(layout="wide")


def build_reader():

    pd_reader = dict()

    pd_reader[".csv"] = pd.read_csv
    pd_reader[".txt"] = pd.read_csv
    pd_reader[".parquet"] = pd.read_parquet
    pd_reader[".xls"] = pd.read_excel
    pd_reader[".xlsx"] = pd.read_excel

    return pd_reader


@st.cache_data
def read_pandas(
    file_name: str, _pre_process: Callable[[pd.DataFrame], pd.DataFrame] = None
) -> pd.DataFrame:

    try:
        _, extension = os.path.splitext(file_name.name)  # type: ignore
    except:
        _, extension = os.path.splitext(file_name)

    extension = extension.lower()
    reader = build_reader()
    df = reader[extension](file_name)

    if _pre_process is not None:
        df = _pre_process(df)

    return df


def file_uploader(
    message: str, pre_process: Callable[[pd.DataFrame], pd.DataFrame] = None  # type: ignore
) -> pd.DataFrame:
    uploaded_file = st.sidebar.file_uploader(message)

    df = None

    if st.sidebar.button("Clear All"):
        # Clear values from *all* all in-memory and on-disk data caches:
        # i.e. clear values from both square and cube
        st.cache_data.clear()

    if uploaded_file is not None:
        df = read_pandas(uploaded_file, pre_process)  # type: ignore

    return df  # type: ignore


def make_time_table():
    dt = dict()
    tslot = 0
    for h in range(24):
        for m in range(0, 60, 5):
            tslot += 1
            dt[f"{h:02d}:{m:02d}:00"] = tslot
    return dt


def make_time_table_week():
    m = list()
    for i in range(6):
        m.append([0 for x in range(60 // 5 * 24)])
    return m


def get_time_slots(dt, inicio, fim):
    try:
        aula = list()
        for i in range(dt[inicio], dt[fim]):
            # is not in 105-107,
            aula.append(i)
    except:
        return list()
    return aula


def preprocess_pandas(df):
    df = df.fillna("")
    df["NOME_DOCENTE"] = df["NOME_DOCENTE"].apply(lambda x: x.strip())

    return df


def calculate_horas_aula(df):
    prof_disciple = defaultdict(lambda: "NAO LISTADO")
    prof_turma = defaultdict(lambda: list())
    time_table = make_time_table()
    professor_time_table = defaultdict(lambda: defaultdict(lambda: set()))
    room_time_table = defaultdict(lambda: defaultdict(lambda: set()))
    m = make_time_table_week()
    horas_em_sala = dict()

    for _, row in df.iterrows():
        cod_d_t = f"{row['COD_DISCIPLINA']}: {row['COD_TURMA']}"
        prof_disciple[cod_d_t] = row["NOME_DOCENTE"]
        prof_turma[row["NOME_DOCENTE"]].append(cod_d_t)
        slots = get_time_slots(time_table, row["HR_INICIO"], row["HR_FIM"])

        for i in slots:
            professor_time_table[row["NOME_DOCENTE"]][row["ITEM_TABELA"]].add(i)
            room_time_table[row["NUM_SALA"]][row["ITEM_TABELA"]].add(i)

    for k in sorted(professor_time_table.keys()):
        v = professor_time_table[k]
        total_slots = 0
        for week_day, slots in v.items():
            if week_day == 2:
                day_i = 0
            elif week_day == 3:
                day_i = 1
            elif week_day == 4:
                day_i = 2
            elif week_day == 5:
                day_i = 3
            elif week_day == 6:
                day_i = 4
            else:
                day_i = 5
            for s in slots:
                m[day_i][s] += 1
            total_slots += len(slots)
        hs = (total_slots * 5) // 60
        ms = (total_slots * 5) % 60
        horas_em_sala[k] = (f"{hs: 02}: {ms: 02}", ms + hs * 60)

    return horas_em_sala


def professor():
    st.header("Relatório de Horários")
    st.subheader("Departamento de Educação Superior - Cefet/RJ")

    df = file_uploader("Escolha o arquivo", preprocess_pandas)

    if df is None:
        st.stop()

    horas_aula = calculate_horas_aula(df)

    name = st.sidebar.selectbox(
        "Nome do Professor", sorted(df.NOME_DOCENTE.unique()), key="name"
    )

    horas_em_sala = calculate_horas_aula(df)

    cond = df.NOME_DOCENTE.str.contains(st.session_state.name.upper())

    selection = df[cond]
    curso_disciplina = selection.COD_CURSO.unique()
    nome_professor = selection.NOME_DOCENTE.unique()[0]
    num_turmas = len(selection.COD_TURMA.unique())
    num_disciplinas = len(selection.COD_DISCIPLINA.unique())

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"Curso: {curso_disciplina}")
        st.write(f"Nome: {nome_professor}")
    with col2:
        st.write(f"Qnt disciplinas: {num_disciplinas}")
        st.write(f"Qnt turmas: {num_turmas}")
        # NOME_DOCENTE = df.NOME_DOCENTE.str.contains(
        #     st.session_state.name.upper()).unique()[0]
        try:
            horas_aula = float(horas_em_sala[nome_professor][1]) / 50
            st.write(
                f"Horas em sala: {horas_em_sala[nome_professor][0]}h ({horas_aula} tempos)"
            )
        except:
            st.write(f"Horas em sala: sem informação")

    st.markdown("---")

    aula_sabado = False

    nt_events = list()
    events = list()
    for _, row in df[cond].iterrows():
        cod_d_t = f"{row['COD_DISCIPLINA']}-{row['COD_TURMA']}"
        hr_inicio = str(row["HR_INICIO"])
        hr_fim = str(row["HR_FIM"])
        dow = int(row["ITEM_TABELA"]) - 2
        if dow >= 0:
            events.append(
                Event(
                    day_of_week=dow,
                    start=hr_inicio[0:5],
                    end=hr_fim[0:5],
                    title=cod_d_t,
                    notes=f"{row['NOME_DISCIPLINA']}, {row['NUM_SALA']}, {row['VAGAS_OCUPADAS']} inscritos",
                    style=EventStyles.GREEN,
                ),
            )
            if dow == 6:
                aula_sabado = True
        else:
            nt_events.append(
                f"{row['COD_DISCIPLINA']}: {row['COD_TURMA']} : {row['NOME_DISCIPLINA']} - {row['NUM_SALA']} - {row['VAGAS_OCUPADAS']}"
            )

    config = CalendarConfig(
        lang="pt",
        title=f"Grade Horária - {name}",
        dates="Seg - Sab" if aula_sabado else "Seg - Sex",
        hours="6 - 22",
        show_date=False,
        legend=False,
        title_vertical_align="top",
    )

    try:
        data.validate_config(config)
        data.validate_events(events, config)
        calendar = Calendar.build(config)
        calendar.add_events(events)
        calendar.save("calendario.png")

        st.image("calendario.png")

        for od in nt_events:
            st.write(od)
    except:
        pass

    with st.expander("Resultado da seleção"):
        df[cond]


def sala():
    st.header("Relatório de Horários")
    st.subheader("Departamento de Educação Superior - Cefet/RJ")

    df = file_uploader("Choose a file", preprocess_pandas)

    if df is None:
        st.stop()

    horas_aula = calculate_horas_aula(df)

    name = st.sidebar.selectbox("Sala", sorted(df.NUM_SALA.unique()), key="name")

    horas_em_sala = calculate_horas_aula(df)

    cond = df.NUM_SALA.str.contains(st.session_state.name.upper())

    selection = df[cond]
    curso_disciplina = selection.COD_CURSO.unique()
    nome_sala = selection.NUM_SALA.unique()[0]
    num_turmas = len(selection.COD_TURMA.unique())
    num_disciplinas = len(selection.COD_DISCIPLINA.unique())

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"Curso: {curso_disciplina}")
        st.write(f"Nome: {nome_sala}")
    with col2:
        st.write(f"Qnt disciplinas: {num_disciplinas}")
        st.write(f"Qnt turmas: {num_turmas}")
        # NOME_DOCENTE = df.NOME_DOCENTE.str.contains(
        #     st.session_state.name.upper()).unique()[0]
        try:
            horas_aula = float(horas_em_sala[nome_sala][1]) / 50
            st.write(
                f"Horas em sala: {horas_em_sala[nome_sala][0]}h ({horas_aula} tempos)"
            )
        except:
            st.write(f"Horas em sala: sem informação")

    st.markdown("---")

    aula_sabado = False

    nt_events = list()
    events = list()
    conjunto_de_sobreposicao = set()
    for _, row in df[cond].iterrows():
        cod_d_t = f"{row['COD_DISCIPLINA']}-{row['COD_TURMA']}"
        hr_inicio = str(row["HR_INICIO"])
        hr_fim = str(row["HR_FIM"])
        dow = int(row["ITEM_TABELA"]) - 2
        sob_key = f"{row['COD_DISCIPLINA']}-{hr_inicio}-{hr_fim}"
        if not sob_key in conjunto_de_sobreposicao:
            conjunto_de_sobreposicao.add(sob_key)
            if dow >= 0:
                events.append(
                    Event(
                        day_of_week=dow,
                        start=hr_inicio[0:5],
                        end=hr_fim[0:5],
                        title=cod_d_t,
                        notes=f"{row['NOME_DISCIPLINA']}, {row['NOME_DOCENTE']}, {hr_inicio}-{hr_fim}",
                        style=EventStyles.GREEN,
                    ),
                )
                if dow == 6:
                    aula_sabado = True
            else:
                nt_events.append(
                    f"{row['COD_DISCIPLINA']}: {row['COD_TURMA']} : {row['NOME_DISCIPLINA']} - {row['NUM_SALA']} - {row['VAGAS_OCUPADAS']}"
                )

    config = CalendarConfig(
        lang="pt",
        title=f"Grade Horária de {name}",
        dates="Seg - Sab" if aula_sabado else "Seg - Sex",
        hours="6 - 22",
        show_date=False,
        legend=False,
        title_vertical_align="top",
    )

    try:
        data.validate_config(config)
        data.validate_events(events, config)
        calendar = Calendar.build(config)
        calendar.add_events(events)
        calendar.save("sala.png")
        st.image("sala.png")

        for od in nt_events:
            st.write(od)
    except:
        pass

    with st.expander("Resultado da seleção"):
        df[cond]

    with st.expander("Professores que usam a Sala"):
        df.loc[cond, "NOME_DOCENTE"]


def intro():
    st.header("Relatório de Horários")
    st.subheader("Departamento de Educação Superior - Cefet/RJ")


def main():
    st_init()
    page_names_to_funcs = {
        "—": intro,
        "Professor": professor,
        "Sala": sala,
    }
    demo_name = st.sidebar.selectbox("Choose a demo", page_names_to_funcs.keys())
    page_names_to_funcs[demo_name]()

    return


if __name__ == "__main__":
    main()
