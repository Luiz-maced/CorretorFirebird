from flask import Flask, request, jsonify, render_template_string
import fdb

app = Flask(__name__)

html_form = """
<!DOCTYPE html>
<html>
<head>
    <title>API.FDB</title>
    <script>
        function comparar() {
            var data = {
                banco_principal: document.getElementById('banco_principal').value,
                banco_espelho: document.getElementById('banco_espelho').value,
                usuario: document.getElementById('usuario').value,
                senha: document.getElementById('senha').value
            };

            fetch('/comparar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('resultado').innerText = data.alter_table.join("\\n");
            })
            .catch(error => alert('Erro: ' + error));
        }
    </script>
</head>
<body>
    <h2>API - INSIRA DOS DADOS</h2>
    <label>Banco Principal:</label> <input type="text" id="banco_principal" placeholder="Caminho do banco"><br>
    <label>Banco Espelho:</label> <input type="text" id="banco_espelho" placeholder="Caminho do banco"><br>
    <label>Usuário:</label> <input type="text" id="usuario" value="SYSDBA"><br>
    <label>Senha:</label> <input type="password" id="senha" value="masterkey"><br>
    <button onclick="comparar()">Comparar</button>

    <h3>RESULT:</h3>
    <pre id="resultado"></pre>
</body>
</html>
"""
def mapear_tipo(tipo, tamanho):
    tipos_firebird = {
    7: "SMALLINT",
    8: "INTEGER",
    9: "QUAD",
    10: "FLOAT",
    12: "DATE",
    13: "TIME",
    14: f"CHAR({tamanho})",
    16: f"NUMERIC ({tamanho})",
    23: "BOOLEAN",
    27: "DOUBLE",
    35: "TIMESTAMP",
    37: f"VARCHAR({tamanho})",
    40: "CSTRING",
    45: "BLOB_ID",
    261: "BLOB"
}
    return tipos_firebird.get(tipo, "UNKNOWN")

# Obtém a estrutura do banco
def get_db_structure(db_path, user, password):
    conn = fdb.connect(dsn=db_path, user=user, password=password)
    cur = conn.cursor()
    
    cur.execute("""
    SELECT 
    RF.RDB$RELATION_NAME AS TABELA, 
    RF.RDB$FIELD_NAME AS COLUNA,
    F.RDB$FIELD_TYPE AS TIPO, 
    F.RDB$FIELD_LENGTH AS TAMANHO
    FROM RDB$RELATION_FIELDS RF
    LEFT JOIN RDB$FIELDS F 
    ON RF.RDB$FIELD_SOURCE = F.RDB$FIELD_NAME
    WHERE RF.RDB$RELATION_NAME NOT LIKE 'RDB$%'

    """)

    estrutura = {}
    for tabela, coluna, tipo, tamanho in cur.fetchall():
        tabela, coluna = tabela.strip(), coluna.strip()
        if tabela not in estrutura:
            estrutura[tabela] = {}
        estrutura[tabela][coluna] = (tipo, tamanho)

    conn.close()
    return estrutura

def gerar_alter_table(estrutura_principal, estrutura_espelho):
    """Compara os bancos e gera ALTER TABLE para colunas e CREATE TABLE para tabelas novas"""
    comandos = []

    for tabela, colunas in estrutura_espelho.items():
        if tabela not in estrutura_principal:
            comando_create = f"CREATE TABLE {tabela} (\n"
            colunas_def = []
            
            for coluna, (tipo, tamanho) in colunas.items():
                tipo_sql = mapear_tipo(tipo, tamanho) 
                colunas_def.append(f"    {coluna} {tipo_sql}")
            
            comando_create += ",\n".join(colunas_def) + "\n);"
            comandos.append(comando_create)

        else:
            for coluna, (tipo, tamanho) in colunas.items():
                if coluna not in estrutura_principal[tabela]:
                    tipo_sql = mapear_tipo(tipo, tamanho)
                    comando = f"ALTER TABLE {tabela} ADD {coluna} {tipo_sql};"
                    comandos.append(comando)

    return comandos

@app.route('/')
def index():
    return render_template_string(html_form)

@app.route('/comparar', methods=['POST'])
def comparar():
    data = request.json
    try:
        estrutura_principal = get_db_structure(data["banco_principal"], data["usuario"], data["senha"])
        estrutura_espelho = get_db_structure(data["banco_espelho"], data["usuario"], data["senha"])

        alter_commands = gerar_alter_table(estrutura_principal, estrutura_espelho)

        return jsonify({"status": "success", "alter_table": alter_commands})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
