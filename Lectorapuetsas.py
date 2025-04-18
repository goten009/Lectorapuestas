import streamlit as st
import easyocr
import pandas as pd
import tempfile
import requests
import re
from PIL import Image

API_KEY = "63a713b7e92435abb05ff969dce291fe"
HEADERS = {"x-apisports-key": API_KEY}

def obtener_stat(stats, tipo):
    for s in stats:
        if s["type"].lower() == tipo.lower():
            return s["value"]
    return "N/D"

def buscar_partido_en_api(nombre_equipo):
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return None
    data = res.json().get("response", [])
    for partido in data:
        home = partido["teams"]["home"]["name"].lower()
        away = partido["teams"]["away"]["name"].lower()
        if nombre_equipo.lower() in home or nombre_equipo.lower() in away:
            stats = partido.get("statistics", [])
            stats_home = stats[0]["statistics"] if len(stats) > 0 and "statistics" in stats[0] else []
            stats_away = stats[1]["statistics"] if len(stats) > 1 and "statistics" in stats[1] else []
            return {
                "fixture": f"{partido['teams']['home']['name']} vs {partido['teams']['away']['name']}",
                "minute": partido["fixture"]["status"].get("elapsed", "N/D"),
                "score": f"{partido['goals']['home']} - {partido['goals']['away']}",
                "yellow_cards": f"{obtener_stat(stats_home, 'Yellow Cards')} - {obtener_stat(stats_away, 'Yellow Cards')}",
                "red_cards": f"{obtener_stat(stats_home, 'Red Cards')} - {obtener_stat(stats_away, 'Red Cards')}",
                "corners": f"{obtener_stat(stats_home, 'Corner Kicks')} - {obtener_stat(stats_away, 'Corner Kicks')}"
            }
    return None

st.set_page_config(page_title="🎟️ Lector de Ticket + API", layout="centered")
st.title("🎟️ Escanea tu Ticket y Consulta el Estado")

imagen = st.file_uploader("📤 Sube tu ticket de apuestas", type=["jpg", "jpeg", "png"])

if imagen:
    st.image(imagen, caption="🎟️ Ticket cargado", use_container_width=True)

    with st.spinner("🧠 Procesando ticket..."):
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(imagen.read())
        temp_file.close()

        reader = easyocr.Reader(['es'], gpu=False)
        resultados = reader.readtext(temp_file.name, detail=0)
        texto = [line.strip() for line in resultados if isinstance(line, str) and len(line.strip()) > 0]

        tabla_apuestas = []
        ticket_perdido = False
        i = 0

        while i < len(texto):
            linea = texto[i].lower()
            anterior = texto[i - 1].strip() if i > 0 else ""
            siguiente = texto[i + 1].strip() if i + 1 < len(texto) else ""
            mercado = ""
            equipo = ""
            seleccion = ""

            if "resultado final" in linea:
                mercado = "Resultado Final"
                seleccion = anterior
                equipo = siguiente
                i += 2
            elif "total de goles" in linea:
                mercado = "Total de Goles"
                seleccion = anterior
                equipo = siguiente
                i += 2
            elif "total de tarjetas" in linea:
                mercado = "Total de Tarjetas"
                seleccion = anterior
                equipo = siguiente
                i += 2
            elif "total de tiros de esquina" in linea:
                mercado = "Total de Corners"
                seleccion = anterior
                equipo = siguiente
                i += 2
            elif "doble oportunidad" in linea:
                mercado = "Doble Oportunidad"
                seleccion = texto[i - 2].strip() if i > 1 else anterior
                equipo = siguiente
                i += 2
            elif "ambos equipos marcarán" in linea:
                mercado = "Ambos Marcan"
                seleccion = anterior
                equipo = siguiente
                i += 2
            else:
                i += 1
                continue

            clave = f"estado_{i}_{seleccion}_{mercado}_{equipo}".replace(" ", "_").lower()

            if ticket_perdido:
                estado = "Perdida"
                fondo = "#f8d7da"
                texto_color = "#721c24"
                st.markdown(
                    f"""
                    <div style="background-color: {fondo}; padding: 10px; border-radius: 8px; margin-bottom: 10px; color: {texto_color};">
                        <strong>🧾 Selección:</strong> {seleccion}<br>
                        <strong>🧠 Mercado:</strong> {mercado}<br>
                        <strong>🏟️ Equipo:</strong> {equipo}<br>
                        <strong>🎯 Estado:</strong> ❌ Anulado por apuesta fallida anterior
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                estado = st.radio(
                    f"📝 ¿Estado de la apuesta '{seleccion}'?",
                    options=["Pendiente", "Ganada", "Perdida"],
                    index=0,
                    key=clave,
                    horizontal=True
                )
                if estado == "Ganada":
                    fondo = "#d4edda"
                    texto_color = "#155724"
                elif estado == "Perdida":
                    fondo = "#f8d7da"
                    texto_color = "#721c24"
                    ticket_perdido = True
                else:
                    fondo = "#f8f9fa"
                    texto_color = "#212529"

                st.markdown(
                    f"""
                    <div style="background-color: {fondo}; padding: 10px; border-radius: 8px; margin-bottom: 10px; color: {texto_color};">
                        <strong>🧾 Selección:</strong> {seleccion}<br>
                        <strong>🧠 Mercado:</strong> {mercado}<br>
                        <strong>🏟️ Equipo:</strong> {equipo}<br>
                        <strong>🎯 Estado:</strong> <span style="font-weight: bold;">{estado}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            tabla_apuestas.append({
                "Selección": seleccion,
                "Equipo": equipo,
                "Mercado": mercado,
                "Estado": estado
            })

        df = pd.DataFrame(tabla_apuestas)
        st.subheader("📊 Resumen del Ticket")
        st.dataframe(df)
        st.download_button("⬇️ Descargar ticket como CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="ticket.csv", mime="text/csv")

        estados = df["Estado"].tolist()
        if "Perdida" in estados:
            st.error("💥 Ticket perdido por al menos una apuesta fallida.")
        elif all(e == "Ganada" for e in estados):
            st.success("🏆 ¡Felicidades! ¡Ganaste el ticket completo! 🎉🎉🎉")
            st.markdown("<h1 style='font-size: 64px;'>🎊🎉🔥</h1>", unsafe_allow_html=True)
        else:
            st.warning("⌛ El ticket está en juego. Aún hay apuestas pendientes.")

        # Mostrar estado en vivo desde API-Football
        st.subheader("📡 Datos en Vivo desde API-Football:")
        equipos_consultados = set(df["Equipo"].tolist())
        for equipo in equipos_consultados:
            resultado = buscar_partido_en_api(equipo)
            if resultado:
                st.success(f"**{resultado['fixture']}**\n\n- ⏱ Minuto: {resultado['minute']}\n- 🔢 Marcador: {resultado['score']}\n- 🟨 Amarillas: {resultado['yellow_cards']}\n- 🟥 Rojas: {resultado['red_cards']}\n- 🥅 Corners: {resultado['corners']}")
            else:
                st.warning(f"No se encontraron datos en vivo para: {equipo}")
