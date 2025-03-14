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

def comparar_nomes(nome1, nome2):
    """Compara dois nomes e retorna um índice de similaridade."""
    return difflib.SequenceMatcher(None, nome1.lower(), nome2.lower()).ratio()

def organizar_por_fornecedor(arquivos):
    agrupados = {}
    fornecedores = {}
    comprovantes = []
    st.write("### Arquivos detectados:")
    
    for arquivo in arquivos:
        nome = arquivo.name
        st.write(f"🔹 {nome}")
        texto_pdf = extrair_texto_pdf(arquivo)
        valores_pdf = encontrar_valores_nf(texto_pdf) if nome.startswith("(BTG)") or nome.startswith("(INTER)") or nome.startswith("(BV)") or "reembolso" in nome.lower() else set()
        linha_digitavel = encontrar_linha_digitavel(texto_pdf)
        
        if nome.startswith("(BTG)") or nome.startswith("(INTER)") or nome.startswith("(BV)") or "reembolso" in nome.lower():
            fornecedor_nome = encontrar_nome_fornecedor(texto_pdf, "documento")
            if fornecedor_nome:
                agrupados[nome] = {"nf": arquivo, "comprovantes": [], "fornecedor": fornecedor_nome, "valores": valores_pdf, "linha": linha_digitavel}
                fornecedores[fornecedor_nome.lower()] = nome
            st.write(f"✅ {nome} identificado como DOCUMENTO PRINCIPAL para {fornecedor_nome}")
        elif nome.lower().startswith("pix"):
            fornecedor_nome = encontrar_nome_fornecedor(texto_pdf, "comprovante")
            valores_pdf = encontrar_valores_nf(texto_pdf)
            linha_comprovante = encontrar_linha_digitavel(texto_pdf)
            comprovantes.append((arquivo, texto_pdf, valores_pdf, fornecedor_nome, linha_comprovante))
    
    for arquivo, texto_pdf, valores_comprovante, fornecedor_comprovante, linha_comprovante in comprovantes:
        nome = arquivo.name
        melhor_match = None
        maior_similaridade = 0.0

        for fornecedor, chave in fornecedores.items():
            valores_nf = agrupados[chave]["valores"]
            linha_nf = agrupados[chave]["linha"]
            
            if valores_comprovante & valores_nf:
                agrupados[chave]["comprovantes"].append(arquivo)
                st.write(f"🔗 {nome} associado a {chave} pelo valor correspondente")
                break
            elif linha_comprovante and linha_nf and linha_comprovante == linha_nf:
                agrupados[chave]["comprovantes"].append(arquivo)
                st.write(f"🔗 {nome} associado a {chave} pela linha digitável")
                break
            
            similaridade = comparar_nomes(fornecedor_comprovante, fornecedor)
            if similaridade > maior_similaridade:
                melhor_match = chave
                maior_similaridade = similaridade
        
        if melhor_match and maior_similaridade > 0.7:
            agrupados[melhor_match]["comprovantes"].append(arquivo)
            st.write(f"🔗 {nome} associado a {melhor_match} pelo nome do fornecedor (similaridade {maior_similaridade:.2f})")
    
    pdf_resultados = {}
    temp_zip_dir = tempfile.mkdtemp()
    zip_path = os.path.join(tempfile.gettempdir(), "comprovantes_agrupados.zip")
    
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for chave, docs in agrupados.items():
            if docs["comprovantes"]:
                merger = PdfMerger()
                arquivos_adicionados = set()
                
                for pdf in docs["comprovantes"] + [docs["nf"]]:
                    if pdf and pdf.name not in arquivos_adicionados:
                        temp_path = os.path.join(tempfile.gettempdir(), pdf.name.replace(" ", "_"))
                        with open(temp_path, "wb") as temp_file:
                            temp_file.write(pdf.getbuffer())  
                        merger.append(temp_path)
                        arquivos_adicionados.add(pdf.name)
                
                nome_arquivo_final = docs["nf"].name
                caminho_saida = os.path.join(temp_zip_dir, nome_arquivo_final)
                merger.write(caminho_saida)
                merger.close()
                zipf.write(caminho_saida, arcname=nome_arquivo_final)
                pdf_resultados[chave] = caminho_saida
                st.write(f"📂 Arquivo final gerado: {nome_arquivo_final}")
            else:
                st.warning(f"⚠️ Nenhum comprovante encontrado para {docs['nf'].name}")
    
    return pdf_resultados, zip_path
if __name__ == "__main__":
    st.title("Agrupador de Comprovantes de Pagamento")
    arquivos = st.file_uploader("Envie seus arquivos", accept_multiple_files=True)
    if arquivos:
        organizar_por_fornecedor(arquivos)



