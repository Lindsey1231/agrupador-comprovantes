import streamlit as st
import os
import tempfile
from PyPDF2 import PdfMerger, PdfReader

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF para buscar o nome do fornecedor."""
    try:
        reader = PdfReader(arquivo)
        texto = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
        return texto.lower()
    except:
        return ""

def organizar_por_fornecedor(arquivos):
    agrupados = {}
    st.write("### Arquivos detectados:")
    
    for arquivo in arquivos:
        nome = arquivo.name
        st.write(f"🔹 {nome}")
        texto_pdf = extrair_texto_pdf(arquivo)
        
        if nome.startswith(("(BTG)", "(INTER)", "(BV)")):
            chave = nome.split("-", 1)[0].strip()  # Pega o banco e o tipo de pagamento
            if chave not in agrupados:
                agrupados[chave] = []
            agrupados[chave].append(arquivo)
            st.write(f"✅ {nome} identificado como DOCUMENTO PRINCIPAL")
        else:
            # Associar comprovante ao fornecedor correto pelo conteúdo do PDF
            for chave, lista in agrupados.items():
                if chave.lower() in texto_pdf:
                    lista.append(arquivo)
                    st.write(f"🔗 {nome} associado a {chave}")
                    break
    
    pdf_resultados = {}
    
    for chave, lista_arquivos in agrupados.items():
        if len(lista_arquivos) > 1:
            merger = PdfMerger()
            temp_files = []
            
            for pdf in lista_arquivos:
                temp_path = os.path.join(tempfile.gettempdir(), pdf.name.replace(" ", "_"))
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(pdf.getbuffer())  
                temp_files.append(temp_path)
                merger.append(temp_path)
            
            nome_arquivo_final = lista_arquivos[0].name  # Usa o nome do primeiro documento como final
            caminho_saida = os.path.join(tempfile.gettempdir(), nome_arquivo_final)
            merger.write(caminho_saida)
            merger.close()
            pdf_resultados[chave] = caminho_saida
            st.write(f"📂 Arquivo final gerado: {nome_arquivo_final}")
        else:
            st.warning(f"⚠️ Nenhum comprovante encontrado para {chave}")
    
    return pdf_resultados

# Interface Streamlit
st.title("Agrupador de Comprovantes de Pagamento")

uploaded_files = st.file_uploader("Arraste os arquivos aqui", accept_multiple_files=True, type=["pdf"])

if uploaded_files:
    st.write("### Arquivos recebidos:")
    for file in uploaded_files:
        st.write(f"✅ {file.name}")
    
    if st.button("Juntar PDFs"):
        st.write("🔄 Processando arquivos... Aguarde.")
        resultados = organizar_por_fornecedor(uploaded_files)

        if not resultados:
            st.error("Nenhum arquivo foi processado. Verifique os nomes e tente novamente.")

        for chave, resultado in resultados.items():
            with open(resultado, "rb") as file:
                st.download_button(
                    label=f"Baixar {chave}",
                    data=file,
                    file_name=chave,
                    mime="application/pdf"
                )
