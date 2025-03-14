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

def classificar_arquivo(nome):
    """Classifica o tipo de arquivo baseado no nome."""
    if any(kw in nome.lower() for kw in ["comprovante", "pix", "transferencia", "deposito"]):
        return "comprovante"
    return "documento"

def organizar_por_valor(arquivos):
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
        tipo_arquivo = classificar_arquivo(nome)
        info_arquivos.append((arquivo, nome, valores, tipo_arquivo))
    
    for comprovante, nome_comp, valores_comp, tipo_comp in info_arquivos:
        if tipo_comp != "comprovante":
            continue
        
        nome_referencia = None
        for doc, nome_doc, valores_doc, tipo_doc in info_arquivos:
            if tipo_doc == "documento" and valores_comp & valores_doc:
                nome_referencia = nome_doc
                break
        
        if nome_referencia is None:
            nome_referencia = f"Sem Correspondência - {nome_comp}"
        
        if nome_referencia not in agrupados:
            agrupados[nome_referencia] = []
        
        agrupados[nome_referencia].append(comprovante)
        for doc, nome_doc, valores_doc, tipo_doc in info_arquivos:
            if tipo_doc == "documento" and valores_comp & valores_doc:
                agrupados[nome_referencia].append(doc)
    
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for nome_final, arquivos in agrupados.items():
            merger = PdfMerger()
            for doc in arquivos:
                merger.append(doc)
            output_filename = nome_final
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
            pdf_resultados, zip_path = organizar_por_valor(arquivos)
            
            for nome, caminho in pdf_resultados.items():
                with open(caminho, "rb") as f:
                    st.download_button(label=f"📄 Baixar {nome}", data=f, file_name=nome, mime="application/pdf")
            
            with open(zip_path, "rb") as f:
                st.download_button(label="📥 Baixar todos como ZIP", data=f, file_name="comprovantes_agrupados.zip", mime="application/zip")

if __name__ == "__main__":
    main()
