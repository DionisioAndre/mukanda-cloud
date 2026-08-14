# Guia de Teste via Frontend - Network Drive

## Pré-requisitos

- Servidor Django rodando: http://127.0.0.1:8000/
- Frontend Vite rodando: http://localhost:5173/
- Windows 7 ou superior
- Permissões de administrador (para mapeamento de drives)

---

## Acesso à Página de Teste

### 1. Abrir o Navegador

Acesse: **http://localhost:5173/network-drive-test**

### 2. Visão Geral da Página

A página contém 3 seções principais:
- **Drives Mapeados**: Lista de drives atualmente mapeados
- **Mapear Compartilhamento SMB**: Formulário para mapear novos drives
- **Exemplos de Uso**: Exemplos de caminhos SMB comuns

---

## Teste 1: Listar Drives Atuais

### Passo a Passo

1. Na seção "Drives Mapeados", clique em **"🔄 Atualizar"**
2. Verifique a lista de drives
3. Se não houver drives, aparecerá "Nenhum drive mapeado"

### Resultado Esperado

```
✅ 0 drive(s) encontrado(s)
Nenhum drive mapeado
```

---

## Teste 2: Mapear Compartilhamento Local

### Passo a Passo

1. **Preencha o formulário:**
   - **Caminho SMB:** `\\localhost\c$\Users\Public`
   - **Letra do Drive:** Deixe vazio (será auto-selecionado)
   - **Usuário:** Deixe vazio
   - **Senha:** Deixe vazio
   - **Persistente:** Marque a caixa

2. Clique em **"📂 Mapear Drive"**

3. Aguarde a mensagem de sucesso

### Resultado Esperado

```
✅ Drive Z: successfully mapped to \\localhost\c$\Users\Public
```

O drive aparecerá na lista de drives mapeados.

---

## Teste 3: Testar Acesso ao Drive

### Passo a Passo

1. Na lista de drives mapeados, localize o drive Z:
2. Clique no botão **"🧪 Testar"**
3. Aguarde o resultado do teste

### Resultado Esperado

```
✅ Drive Z: is accessible
```

---

## Teste 4: Desmapear Drive

### Passo a Passo

1. Na lista de drives mapeados, clique em **"❌ Desmapear"**
2. Confirme a operação
3. O drive será removido da lista

### Resultado Esperado

```
✅ Drive Z: successfully unmapped
```

---

## Teste 5: Mapear com Letra Específica

### Passo a Passo

1. Clique em **"🔍 Auto"** ao lado do campo "Letra do Drive"
2. O sistema preencherá automaticamente uma letra disponível (ex: Y:)
3. Preencha o caminho SMB: `\\localhost\c$\Windows`
4. Clique em **"📂 Mapear Drive"**

### Resultado Esperado

```
✅ Drive Y: successfully mapped to \\localhost\c$\Windows
```

---

## Teste 6: Mapear com Autenticação (Simulado)

### Passo a Passo

1. **Preencha o formulário:**
   - **Caminho SMB:** `\\localhost\c$`
   - **Letra do Drive:** X
   - **Usuário:** Seu usuário do Windows
   - **Senha:** Sua senha do Windows
   - **Persistente:** Desmarque (para teste)

2. Clique em **"📂 Mapear Drive"**

### Resultado Esperado

```
✅ Drive X: successfully mapped to \\localhost\c$
```

---

## Teste 7: Auto-seleção de Drive

### Passo a Passo

1. Deixe o campo "Letra do Drive" vazio
2. Preencha qualquer caminho SMB válido
3. Clique em **"📂 Mapear Drive"**

### Resultado Esperado

O sistema automaticamente selecionará a próxima letra disponível (Z, Y, X, etc.)

---

## Teste 8: Múltiplos Drives

### Passo a Passo

1. Mapeie o primeiro drive com `\\localhost\c$\Users\Public`
2. Mapeie o segundo drive com `\\localhost\c$\Windows`
3. Mapeie o terceiro drive com `\\localhost\c$\Program Files`

### Resultado Esperado

Três drives aparecerão na lista:
- Z: → \\localhost\c$\Users\Public
- Y: → \\localhost\c$\Windows
- X: → \\localhost\c$\Program Files

---

## Teste 9: Verificar no Windows Explorer

### Passo a Passo

1. Após mapear um drive, abra o Windows Explorer
2. Procure pela unidade mapeada (Z:, Y:, etc.)
3. Navegue pelos arquivos
4. Verifique se o acesso está funcionando

### Resultado Esperado

A unidade mapeada aparece como "Network Drive" e é acessível.

---

## Teste 10: Limpeza Completa

### Passo a Passo

1. Clique em **"❌ Desmapear"** em todos os drives mapeados
2. Clique em **"🔄 Atualizar"** para verificar
3. Confirme que a lista está vazia

### Resultado Esperado

```
✅ 0 drive(s) encontrado(s)
Nenhum drive mapeado
```

---

## Exemplos de Caminhos SMB

### NAS Synology
```
\\192.168.1.100\engineering
\\synology-nas\cad-files
```

### Windows Server
```
\\fileserver.company.local\shared-folder
\\server-name\projects
```

### Compartilhamento Local
```
\\localhost\c$\Users\Public
\\127.0.0.1\c$\Windows
\\.\c$\Program Files
```

### Linux Samba
```
\\192.168.1.50\share
\\linux-server\home
```

---

## Solução de Problemas

### Problema: "Erro de conexão"

**Causa:** Servidor Django não está rodando

**Solução:**
```bash
cd DJANGO
python manage.py runserver
```

### Problema: "Caminho da rede não foi encontrado"

**Causa:** Caminho SMB incorreto ou servidor offline

**Solução:**
- Verifique o caminho SMB
- Teste com `\\localhost\c$`
- Verifique se o servidor está acessível

### Problema: "Drive já em uso"

**Causa:** A letra de drive já está mapeada

**Solução:**
- Desmapear o drive existente primeiro
- Ou use outra letra de drive

### Problema: "Acesso negado"

**Causa:** Permissões insuficientes ou credenciais incorretas

**Solução:**
- Execute o navegador como Administrador
- Verifique usuário e senha
- Use compartilhamento público para teste

### Problema: "Nenhum drive disponível"

**Causa:** Todas as letras de Z a D estão em uso

**Solução:**
- Desmapear drives não usados
- Ou use letras fora do range padrão

---

## Checklist de Teste

- [ ] Acessou a página http://localhost:5173/network-drive-test
- [ ] Listou drives atuais
- [ ] Mapeou compartilhamento local
- [ ] Testou acesso ao drive
- [ ] Desmapeou drive
- [ ] Mapeou com letra específica
- [ ] Usou auto-seleção de drive
- [ ] Mapeou múltiplos drives
- [ ] Verificou no Windows Explorer
- [ ] Limpeza completa

---

## Próximos Passos

Após concluir os testes:

1. **Teste com servidor real:**
   - NAS da empresa
   - Windows Server
   - Compartilhamento de rede

2. **Integração com AutoCAD:**
   - Mapear drive com arquivos CAD
   - Abrir arquivos DWG do drive mapeado
   - Verificar performance

3. **Deploy para produção:**
   - Configurar servidor Django de produção
   - Configurar frontend de produção
   - Implementar autenticação

---

## Suporte

Se encontrar problemas:
1. Verifique se os servidores estão rodando
2. Consulte os logs do console
3. Verifique a documentação técnica
4. Teste via comando Windows: `net use Z: \\path\share`

---

*Guia atualizado em 23 de Julho de 2026*
