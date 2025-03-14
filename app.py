import streamlit as st
import os
import tempfile
import re
import difflib
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

def encontrar_valores_nf(texto):
    """Busca valores monetários no PDF e calcula o valor líquido corretamente."""
    padrao_valores = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")  # Formato 1.234,56
    valores_encontrados = padrao_valores.findall(texto)
    valores = set(map(lambda x: float(x.replace(".", "").replace(",", ".")), valores_encontrados))
    
    if not valores:
        return set()
    
    valor_bruto = max(valores, default=0)
    
    impostos_padrao = re.compile(r"(IRRF|PIS|COFINS|CSLL|INSS)[:\s]+(\d{1,3}(?:\.\d{3})*,\d{2})", re.IGNORECASE)
    impostos_encontrados = impostos_padrao.findall(texto)
    impostos = sum(float(valor.replace(".", "").replace(",", ".")) for _, valor in impostos_encontrados)
    
    padrao_nd = re.search(r"Nota de D[eé]bito[:\s]+(\d{1,3}(?:\.\d{3})*,\d{2})", texto)
    valor_nd = float(padrao_nd.group(1).replace(".", "").replace(",", ".")) if padrao_nd else 0
    
    valor_liquido = valor_bruto - impostos - valor_nd
    valores.add(valor_liquido)
    
    return valores

def encontrar_linha_digitavel(texto):
    """Busca a linha digitável no texto e remove pontos e traços para comparação."""
    padrao_linha = re.search(r"(\d{5}\.\d{5}\s\d{5}\.\d{6}\s\d{5}\.\d{6}\s\d{1}\s\d{14})", texto)
    if padrao_linha:
        return re.sub(r"[\.\s-]", "", padrao_linha.group(1))
    return ""

def organizar_por_fornecedor(arquivos):
    st.write("### Processando arquivos...")
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "comprovantes_agrupados.zip")
    pdf_resultados = {}
    agrupados = {}

    for arquivo in arquivos:
        nome = arquivo.name
        texto_pdf = extrair_texto_pdf(arquivo)
        fornecedor_nome = encontrar_nome_fornecedor(texto_pdf, "documento")
        valores_pdf = encontrar_valores_nf(texto_pdf)
        linha_digitavel = encontrar_linha_digitavel(texto_pdf)
        
        if nome.lower().startswith("pix"):
            if fornecedor_nome not in agrupados:
                agrupados[fornecedor_nome] = {"comprovantes": [], "documentos": []}
            agrupados[fornecedor_nome]["comprovantes"].append(arquivo)
        else:
            if fornecedor_nome not in agrupados:
                agrupados[fornecedor_nome] = {"comprovantes": [], "documentos": []}
            agrupados[fornecedor_nome]["documentos"].append(arquivo)
    
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for fornecedor, dados in agrupados.items():
            if dados["comprovantes"] and dados["documentos"]:
                merger = PdfMerger()
                for doc in dados["documentos"]:
                    merger.append(doc)
                for comp in dados["comprovantes"]:
                    merger.append(comp)
                
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
        pdf_resultados, zip_path = organizar_por_fornecedor(arquivos)
        
        for nome, caminho in pdf_resultados.items():
            with open(caminho, "rb") as f:
                st.download_button(f"Baixar {nome}", f, file_name=nome)
        
        with open(zip_path, "rb") as f:
            st.download_button("📥 Baixar todos como ZIP", f, file_name="comprovantes_agrupados.zip")

if __name__ == "__main__":
    main()


