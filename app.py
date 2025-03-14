import streamlit as st
import os
import tempfile
import re
import shutil
import zipfile
from PyPDF2 import PdfMerger, PdfReader

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF para buscar informações."""
    try:
        reader = PdfReader(arquivo)
        texto = " \n".join([page.extract_text() or "" for page in reader.pages])
        return texto
    except:
        return ""

def encontrar_valor(texto):
    """Busca valores monetários no conteúdo do PDF."""
    padrao_valor = re.findall(r"\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})\b", texto)
    return set(padrao_valor) if padrao_valor else set()

def encontrar_nome_fornecedor(texto, tipo_documento):
    """Busca o nome do fornecedor no conteúdo do PDF."""
    if tipo_documento == "comprovante":
        padrao_nome = re.search(r"(?i)nome[:\s]+([A-Za-zÀ-ÖØ-öø-ÿ&\s]+)", texto)
        if padrao_nome:
            return padrao_nome.group(1).strip()
    else:
        padrao_geral = re.compile(r"([A-Za-zÀ-ÖØ-öø-ÿ&\s]+(?:ltda|s\.a\.|me|eireli|ss|associação|empresa|corporation|corp|inc)?)", re.IGNORECASE)
        correspondencias = padrao_geral.findall(texto)
        if correspondencias:
            return correspondencias[0].strip()
    return ""

def organizar_por_valor_e_fornecedor(arquivos):
    st.write("### Processando arquivos...")
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "comprovantes_agrupados.zip")
    pdf_resultados = {}
    agrupados = {}
    
    info_arquivos = []
    
    for arquivo in arquivos:
        nome = arquivo.name
        texto_pdf = extrair_texto_pdf(arquivo)
        valores = encontrar_valor(texto_pdf)
        fornecedor_nome = encontrar_nome_fornecedor(texto_pdf, "documento")
        
        if fornecedor_nome == "":
            fornecedor_nome = "Desconhecido"
        
        info_arquivos.append((arquivo, nome, valores, fornecedor_nome))
    
    for arquivo, nome, valores, fornecedor in info_arquivos:
        correspondente = None
        
        for outro_arquivo, outro_nome, outro_valores, outro_fornecedor in info_arquivos:
            if arquivo != outro_arquivo and valores & outro_valores:
                correspondente = outro_fornecedor
                break
        
        fornecedor_final = correspondente if correspondente else fornecedor
        
        if fornecedor_final not in agrupados:
            agrupados[fornecedor_final] = []
        
        agrupados[fornecedor_final].append(arquivo)
    
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for fornecedor, arquivos in agrupados.items():
            merger = PdfMerger()
            for doc in arquivos:
                merger.append(doc)
            output_filename = f"{fornecedor}.pdf"
            output_path = os.path.join(temp_dir, output_filename)
            merger.write(output_path)
            merger.close()
            pdf_resultados[output_filename] = output_path
            zipf.write(output_path, arcname=output_filename)
            st.write(f"📂 Arquivo gerado: {output_filename}")
    
    return pdf_resultados, zip_path

def main():
    st.title("Agrupador de Comprovantes de Pagamento")
    arquivos = st.file_uploader("Envie seus arquivos", accept_multiple_files=True)
    
    if arquivos:
        if st.button("🔗 Juntar e Processar PDFs"):
            pdf_resultados, zip_path = organizar_por_valor_e_fornecedor(arquivos)
            
            for nome, caminho in pdf_resultados.items():
                with open(caminho, "rb") as f:
                    st.download_button(label=f"📄 Baixar {nome}", data=f, file_name=nome, mime="application/pdf")
            
            with open(zip_path, "rb") as f:
                st.download_button(label="📥 Baixar todos como ZIP", data=f, file_name="comprovantes_agrupados.zip", mime="application/zip")

if __name__ == "__main__":
    main()

