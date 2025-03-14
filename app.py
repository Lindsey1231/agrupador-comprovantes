import streamlit as st
import os
import tempfile
import re
import shutil
import zipfile
from PyPDF2 import PdfMerger, PdfReader
from difflib import SequenceMatcher

def extrair_texto_pdf(arquivo):
    """Extrai texto do PDF garantindo melhor leitura."""
    try:
        reader = PdfReader(arquivo)
        texto = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                texto.append(page_text)
        return " \n".join(texto)
    except Exception as e:
        return f"Erro na extração do texto: {str(e)}"

def encontrar_valor(texto):
    """Busca valores monetários no conteúdo do PDF."""
    padrao_valor = re.findall(r"\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})\b", texto)
    valores_processados = set()
    for valor in padrao_valor:
        try:
            valores_processados.add(float(valor.replace('.', '').replace(',', '.')))
        except ValueError:
            continue
    return valores_processados

def encontrar_cnpj(texto):
    """Busca CNPJs no conteúdo do PDF e padroniza a formatação."""
    padrao_cnpj = re.findall(r"\b\d{2}[.\/]?\d{3}[.\/]?\d{3}[\/\-]?\d{4}[\/\-]?\d{2}\b", texto)
    return {re.sub(r'[^\d]', '', cnpj) for cnpj in padrao_cnpj} if padrao_cnpj else set()

def encontrar_nome_fornecedor(texto):
    """Busca um nome de fornecedor provável baseado em padrões de texto."""
    padrao_nome = re.findall(r"([A-Z\s&.,-]{5,})", texto)
    return set(padrao_nome) if padrao_nome else set()

def classificar_arquivo(nome):
    """Classifica o tipo de arquivo baseado no nome."""
    if any(kw in nome.lower() for kw in ["comprovante", "pix", "transferencia", "deposito"]):
        return "comprovante"
    return "documento"

def similaridade(a, b):
    """Calcula similaridade entre duas strings."""
    return SequenceMatcher(None, a, b).ratio()

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
        cnpjs = encontrar_cnpj(texto_pdf)
        nomes_fornecedores = encontrar_nome_fornecedor(texto_pdf)
        tipo_arquivo = classificar_arquivo(nome)
        info_arquivos.append((arquivo, nome, valores, cnpjs, nomes_fornecedores, tipo_arquivo))
    
    for doc, nome_doc, valores_doc, cnpjs_doc, nomes_doc, tipo_doc in info_arquivos:
        if tipo_doc != "documento":
            continue
        
        melhor_correspondencia = None
        
        for comprovante, nome_comp, valores_comp, cnpjs_comp, nomes_comp, tipo_comp in info_arquivos:
            if tipo_comp == "comprovante":
                if any(abs(vc - vd) / vd <= 0.005 for vc in valores_comp for vd in valores_doc if vd != 0):
                    melhor_correspondencia = comprovante
                    break
                if not melhor_correspondencia and bool(cnpjs_comp & cnpjs_doc):
                    melhor_correspondencia = comprovante
                if not melhor_correspondencia and any(
                    any(similaridade(nc, nd) > 0.7 for nd in nomes_doc)
                    for nc in nomes_comp
                ):
                    melhor_correspondencia = comprovante
        
        if melhor_correspondencia:
            agrupados[nome_doc] = [melhor_correspondencia, doc]
    
    for comprovante, nome_comp, valores_comp, cnpjs_comp, nomes_comp, tipo_comp in info_arquivos:
        if tipo_comp == "comprovante" and not any(comprovante in lista for lista in agrupados.values()):
            nome_referencia = f"Sem Correspondência - {nome_comp}"
            agrupados[nome_referencia] = [comprovante]
    
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
    
    if arquivos is not None and len(arquivos) > 0:
        if st.button("🔗 Juntar e Processar PDFs"):
            pdf_resultados, zip_path = organizar_por_valor(arquivos)
            
            for nome, caminho in pdf_resultados.items():
                with open(caminho, "rb") as f:
                    st.download_button(label=f"📄 Baixar {nome}", data=f, file_name=nome, mime="application/pdf")
            
            with open(zip_path, "rb") as f:
                st.download_button(label="📥 Baixar todos como ZIP", data=f, file_name="comprovantes_agrupados.zip", mime="application/zip")

if __name__ == "__main__":
    main()

