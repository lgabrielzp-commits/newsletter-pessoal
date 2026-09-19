# Projeto: Newsletter Pessoal Automatizada
## Especificação Completa e Histórico de Desenvolvimento

**Data de Início:** 18 de setembro de 2026  
**Última Atualização:** 19 de setembro de 2026  
**Status:** Em transição para Claude Code (automação e entrega)

---

## 1. Objetivo Geral

Criar uma **newsletter pessoal automática** que:
- Agregue notícias de **finanças/economia**, **política brasileira** e **IA/tecnologia**
- Rode **diariamente** (ou conforme agendado)
- Entregue ao usuário (Gabriel) de forma profissional
- Seja **apresentável** e **interativa**

---

## 2. Histórico de Requisitos e Evolução

### Primeira Iteração (18/09/2026)
**Pedido inicial:**
- Coletar notícias das últimas 24-48h
- Fontes específicas: Folha de S.Paulo, Estadão, G1, InfoMoney, New York Times
- Filtrar apenas notícias substantivas, sem duplicatas
- Organizar por tema: Finanças, Política, IA
- Quando múltiplas fontes cobrem mesma história, incluir **perspectivas divergentes** lado a lado
- Conteúdo do NYT traduzido para português, mantendo termos técnicos em inglês
- Output: **HTML newsletter** estilo publicação profissional
  - Seções claras
  - Headlines, summaries (2-3 linhas)
  - Atribuição de fontes com badges
  - Análise multi-perspectiva onde aplicável

**Resultado:** `newsletter.html` criado com design básico (gradiente roxo, layout simples)

### Segunda Iteração (19/09/2026 - ATUAL)
**Pedido de profissionalização:**

1. **Abas navegáveis no topo**
   - 3 abas: Finanças & Economia | Política Brasil | IA & Tecnologia
   - Click para filtrar conteúdo
   - Apenas uma aba ativa por vez

2. **Notícias expansíveis**
   - Estado padrão: resumo curto (2-3 linhas)
   - Texto visual "Leia mais" (clicável)
   - Ao expandir: 3-4 parágrafos com contexto completo
   - Ao recolher: volta para resumo
   - Toggle visual ("- Ler menos" quando expandido)

3. **Links para fonte original**
   - Aparecem ao expandir a notícia
   - Devem levar diretamente para a matéria específica (não só homepage)
   - Botão visual destacado

4. **Design profissional**
   - Referências: Folha de S.Paulo, Financial Times
   - Cores: Preto (#1a1a1a), vermelho #c41e3a (accent)
   - Tipografia: Sans-serif clean, hierarquia clara
   - Espaçamento generoso
   - Badges sutis (não coloridas)

**Resultado:** `newsletter-v2.html` criado com todas as features acima

### Terceiro Passo (EM ANDAMENTO)
**Requisito de automação:**
- Buscar URLs específicas de cada notícia (não apenas homepage)
- Executar **diariamente** de forma automatizada
- Enviar ao usuário (método TBD: email, push, webhook, etc.)
- Integração com Claude Code para orquestração

---

## 3. Código HTML/CSS/JavaScript Completo

### newsletter-v2.html

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newsletter | Finanças, Política e IA</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
            background: #f8f9fa;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            overflow: hidden;
        }
        
        .header {
            background: #1a1a1a;
            color: white;
            padding: 48px 40px;
            text-align: center;
            border-bottom: 3px solid #c41e3a;
        }
        
        .header h1 {
            font-size: 36px;
            font-weight: 800;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }
        
        .header p {
            font-size: 13px;
            color: #aaa;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .tabs {
            display: flex;
            background: white;
            border-bottom: 1px solid #e0e0e0;
            padding: 0;
        }
        
        .tab-button {
            flex: 1;
            padding: 16px 20px;
            border: none;
            background: white;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            color: #666;
            transition: all 0.2s ease;
            border-bottom: 3px solid transparent;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .tab-button:hover {
            background: #f8f9fa;
            color: #333;
        }
        
        .tab-button.active {
            color: #1a1a1a;
            border-bottom-color: #c41e3a;
            background: #fafafa;
        }
        
        .content {
            padding: 40px;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .news-item {
            margin-bottom: 32px;
            padding-bottom: 32px;
            border-bottom: 1px solid #e8e8e8;
        }
        
        .news-item:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }
        
        .news-header {
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .news-header:hover {
            padding-left: 4px;
        }
        
        .news-title {
            font-size: 18px;
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 10px;
            line-height: 1.35;
        }
        
        .news-summary {
            font-size: 14px;
            line-height: 1.6;
            color: #555;
            margin-bottom: 12px;
        }
        
        .expand-indicator {
            font-size: 12px;
            color: #c41e3a;
            font-weight: 600;
            cursor: pointer;
            display: inline-block;
            margin-top: 8px;
        }
        
        .news-expanded {
            display: none;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #f0f0f0;
        }
        
        .news-expanded.show {
            display: block;
        }
        
        .news-full-text {
            font-size: 14px;
            line-height: 1.65;
            color: #444;
            margin-bottom: 14px;
        }
        
        .news-full-text p {
            margin-bottom: 12px;
        }
        
        .perspective {
            background: #f5f5f5;
            border-left: 3px solid #c41e3a;
            padding: 12px 14px;
            margin: 14px 0;
            font-size: 13px;
            line-height: 1.5;
            color: #555;
        }
        
        .perspective-label {
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 4px;
            font-size: 12px;
        }
        
        .source-link {
            display: inline-block;
            margin-top: 12px;
            padding: 8px 14px;
            background: #f0f0f0;
            border: 1px solid #ddd;
            border-radius: 4px;
            text-decoration: none;
            color: #c41e3a;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        
        .source-link:hover {
            background: #c41e3a;
            color: white;
            border-color: #c41e3a;
        }
        
        .badges {
            margin-top: 12px;
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        
        .badge {
            display: inline-block;
            background: #e8e8e8;
            color: #333;
            padding: 4px 10px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        
        .footer {
            background: #f8f9fa;
            padding: 24px 40px;
            border-top: 1px solid #e0e0e0;
            font-size: 12px;
            color: #777;
            line-height: 1.6;
        }
        
        .footer strong {
            color: #333;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>NEWSLETTER</h1>
            <p>Notícias de Finanças, Política e IA — 18 de Setembro de 2026</p>
        </div>
        
        <div class="tabs">
            <button class="tab-button active" onclick="switchTab('finances')">💰 Finanças & Economia</button>
            <button class="tab-button" onclick="switchTab('politics')">🏛️ Política Brasil</button>
            <button class="tab-button" onclick="switchTab('ai')">🤖 IA & Tecnologia</button>
        </div>
        
        <div class="content">
            <!-- FINANÇAS -->
            <div id="finances" class="tab-content active">
                <div class="news-item">
                    <div class="news-header" onclick="toggleExpand(this)">
                        <div class="news-title">Banco Central reduz Selic para 13,75%</div>
                        <div class="news-summary">O Copom reduziu a taxa básica de juros em 0,25 p.p. em setembro, chegando a 13,75% ao ano — o quinto corte consecutivo. O mercado projeta que a taxa termine 2026 neste patamar.</div>
                        <div class="expand-indicator">+ Leia mais</div>
                    </div>
                    <div class="news-expanded">
                        <div class="news-full-text">
                            <p>O Comitê de Política Monetária (Copom) do Banco Central reduziu a taxa Selic em 0,25 ponto percentual durante sua reunião de 15 e 16 de setembro, chegando a 13,75% ao ano. Este é o quinto corte consecutivo da taxa básica de juros, parte da estratégia de redução que começou no ciclo anterior.</p>
                            <p>Segundo o Boletim Focus mais recente, o mercado financeiro projeta que a Selic termine 2026 neste mesmo patamar de 13,75%. A tendência de redução reflete a estratégia do banco central de estimular a economia em um contexto de pressão inflacionária controlada e crescimento econômico moderado.</p>
                        </div>
                        <div class="badges">
                            <span class="badge">Banco Central</span>
                            <span class="badge">Agência Brasil</span>
                        </div>
                        <a href="https://www.bcb.gov.br" class="source-link">→ Acessar fonte original</a>
                    </div>
                </div>
                
                <div class="news-item">
                    <div class="news-header" onclick="toggleExpand(this)">
                        <div class="news-title">Inflação projetada em 4,90% para 2026</div>
                        <div class="news-summary">O mercado revisou para baixo a expectativa de inflação, de 5% para 4,90%. PIB mantido em 1,89% de crescimento. Analistas destacam incerteza do ambiente externo pelas políticas comerciais dos EUA.</div>
                        <div class="expand-indicator">+ Leia mais</div>
                    </div>
                    <div class="news-expanded">
                        <div class="news-full-text">
                            <p>O mercado financeiro revisou para baixo a expectativa de inflação para o final de 2026, saindo de 5% para 4,90%. A redução reflete melhores condições de oferta e o efeito dos cortes de juros já implementados. O Boletim Focus do Banco Central também mantém a projeção de crescimento do PIB em 1,89% para este ano, indicando crescimento moderado.</p>
                            <p>Os analistas destacam que o ambiente externo continua marcado por incerteza significativa, particularmente devido às políticas comerciais dos EUA, que podem impactar a inflação importada e a dinâmica do câmbio nos próximos trimestres.</p>
                        </div>
                        <div class="badges">
                            <span class="badge">Boletim Focus</span>
                            <span class="badge">Banco Central</span>
                        </div>
                        <a href="https://www.bcb.gov.br/publicacoes/focus" class="source-link">→ Acessar fonte original</a>
                    </div>
                </div>
            </div>
            
            <!-- POLÍTICA -->
            <div id="politics" class="tab-content">
                <div class="news-item">
                    <div class="news-header" onclick="toggleExpand(this)">
                        <div class="news-title">Hugo Motta tensiona Congresso sobre IOF e aumento de deputados</div>
                        <div class="news-summary">O presidente da Câmara continua gerando tensões em torno da revogação do IOF e do aumento de deputados de 513 para 531. A derrubada do decreto afeta bilhões em arrecadação.</div>
                        <div class="expand-indicator">+ Leia mais</div>
                    </div>
                    <div class="news-expanded">
                        <div class="news-full-text">
                            <p>O presidente da Câmara dos Deputados, Hugo Motta, continuou gerando tensões políticas em torno de duas pautas principais: a revogação do Imposto sobre Operações Financeiras (IOF) e a votação sobre o aumento do número de deputados federais de 513 para 531. A derrubada do decreto do IOF foi votada em junho com 383 votos contra apenas 98 a favor do governo, representando derrota clara do Executivo.</p>
                            <p>A medida afeta a arrecadação de bilhões para o orçamento federal, criando pressão significativa sobre as contas públicas. Motta opera sob forte influência do Centrão, mantendo olhos voltados para as eleições de 2026.</p>
                        </div>
                        <div class="perspective">
                            <div class="perspective-label">📰 Perspectivas Divergentes</div>
                            <strong>Folha de S.Paulo:</strong> Analisa a votação como expressão clara de conflito entre o Congresso e o Executivo, com Motta operando sob forte influência do Centrão com olhos voltados às eleições de 2026.<br><br>
                            <strong>Governo Federal:</strong> O ministro Fernando Haddad alertou que a perda de receita do IOF forçará contingenciamentos maiores em emendas parlamentares (até R$ 7,1 bilhões em 2026) e políticas sociais.
                        </div>
                        <div class="badges">
                            <span class="badge">Folha de S.Paulo</span>
                            <span class="badge">CartaCapital</span>
                            <span class="badge">Câmara dos Deputados</span>
                        </div>
                        <a href="https://www2.camara.leg.br" class="source-link">→ Acessar fonte original</a>
                    </div>
                </div>
                
                <div class="news-item">
                    <div class="news-header" onclick="toggleExpand(this)">
                        <div class="news-title">Campanhas presidenciais 2026 em movimento</div>
                        <div class="news-summary">Lula, Tarcísio de Freitas e Flávio Bolsonaro definem posicionamentos. Cenário descrito como um dos mais imprevisíveis da história política recente.</div>
                        <div class="expand-indicator">+ Leia mais</div>
                    </div>
                    <div class="news-expanded">
                        <div class="news-full-text">
                            <p>Com as eleições presidenciais de 2026 se aproximando, os principais candidatos definem seus posicionamentos políticos e estratégias de campanha. Lula (PT) busca consolidar apoio em sua base tradicional enquanto enfrenta pressão econômica crescente e desafios no relacionamento com o Congresso.</p>
                            <p>Tarcísio de Freitas (Republicanos-SP) emerge como uma forte alternativa de centro-direita, enquanto Flávio Bolsonaro (PL) consolida-se como favorito da extrema direita. Analistas descrevem o cenário como um dos mais imprevisíveis da história política recente, com múltiplos atores viáveis e dinâmicas ainda em formação.</p>
                        </div>
                        <div class="badges">
                            <span class="badge">G1</span>
                            <span class="badge">JOTA</span>
                        </div>
                        <a href="https://g1.globo.com" class="source-link">→ Acessar fonte original</a>
                    </div>
                </div>
            </div>
            
            <!-- IA & TECNOLOGIA -->
            <div id="ai" class="tab-content">
                <div class="news-item">
                    <div class="news-header" onclick="toggleExpand(this)">
                        <div class="news-title">Pesquisadores usam Claude para hackear ChatGPT; OpenAI paga bounty</div>
                        <div class="news-summary">Pesquisadores da Hacktron AI usaram Claude para ganhar acesso à conta ChatGPT de um funcionário da OpenAI em menos de 72 horas. OpenAI pagou US$ 6.500 em recompensa.</div>
                        <div class="expand-indicator">+ Leia mais</div>
                    </div>
                    <div class="news-expanded">
                        <div class="news-full-text">
                            <p>Pesquisadores da Hacktron AI usaram Claude para ganhar acesso à conta ChatGPT de um funcionário da OpenAI em menos de 72 horas, chegando até ao repositório GitHub da empresa e dados sobre armazenamento de código-fonte. A equipe reportou responsavelmente sobre a vulnerabilidade descoberta, seguindo as melhores práticas de disclosure responsável.</p>
                            <p>A OpenAI pagou US$ 6.500 (aproximadamente R$ 39 mil) em bug bounty pela descoberta responsável. O incidente ressalta vulnerabilidades significativas de modelos de linguagem a cyberataques coordenados e de engenharia social, evidenciando a importância de verificação de identidade robusta e segurança de contas em sistemas críticos.</p>
                        </div>
                        <div class="badges">
                            <span class="badge">CBS News</span>
                            <span class="badge">Fortune</span>
                            <span class="badge">PYMNTS</span>
                        </div>
                        <a href="https://www.cbsnews.com" class="source-link">→ Acessar fonte original</a>
                    </div>
                </div>
                
                <div class="news-item">
                    <div class="news-header" onclick="toggleExpand(this)">
                        <div class="news-title">Anthropic lança Programa de Verificação em Ciências da Vida (LSVP)</div>
                        <div class="news-summary">Anthropic apresentou avanços em IA para descoberta de medicamentos: novo modo de baixa memória para sistemas com 10+ mil tokens em GPU única, aceleração 4x. Lançou competição de design de proteínas com até US$ 1 mi em créditos.</div>
                        <div class="expand-indicator">+ Leia mais</div>
                    </div>
                    <div class="news-expanded">
                        <div class="news-full-text">
                            <p>Anthropic apresentou avanços significativos em inteligência artificial para descoberta de medicamentos e pesquisa biomolecular. A empresa desenvolveu um novo modo de baixa memória que permite processar sistemas biomoleculares complexos com mais de 10 mil tokens em uma única GPU, alcançando aceleração de 4x em mais de 30 modelos de código aberto.</p>
                            <p>A empresa também lançou uma competição internacional de design de proteínas oferecendo até US$ 1 milhão em créditos de computação. O novo LSVP (Life Sciences Verification Program) oferece acesso a modelos Mythos, Opus e Sonnet com salvaguardas biologicamente específicas para organizações verificadas de pesquisa e saúde.</p>
                        </div>
                        <div class="badges">
                            <span class="badge">Anthropic Research</span>
                            <span class="badge">Claude Life Sciences</span>
                        </div>
                        <a href="https://www.anthropic.com/research" class="source-link">→ Acessar fonte original</a>
                    </div>
                </div>
                
                <div class="news-item">
                    <div class="news-header" onclick="toggleExpand(this)">
                        <div class="news-title">Vídeos com IA entram na batalha política brasileira</div>
                        <div class="news-summary">Vídeos gerados com IA usando Google Veo 3 passaram a ferramentas de crítica política. Conteúdo satiriza decisões de Hugo Motta, circulando massivamente no X com ironia direta.</div>
                        <div class="expand-indicator">+ Leia mais</div>
                    </div>
                    <div class="news-expanded">
                        <div class="news-full-text">
                            <p>Vídeos gerados com inteligência artificial, especialmente usando Google Veo 3, transitaram de experiência estética para ferramenta sofisticada de crítica política no Brasil. Conteúdo criado por cidadãos comuns satiriza decisões de Hugo Motta sobre a revogação do IOF e o aumento do número de deputados federais, circulando massivamente na rede social X (antigo Twitter) com ironia e crítica direta.</p>
                            <p>A mobilização espontânea de usuários evidencia a autonomia que ferramentas generativas de mídia proporcionam ao cidadão comum para criar, editar e distribuir conteúdo político com velocidade exponencial, democratizando o acesso a recursos de produção audiovisual antes disponíveis apenas para grandes produtoras.</p>
                        </div>
                        <div class="badges">
                            <span class="badge">Folha de S.Paulo</span>
                            <span class="badge">agenteGPT</span>
                        </div>
                        <a href="https://www1.folha.uol.com.br" class="source-link">→ Acessar fonte original</a>
                    </div>
                </div>
                
                <div class="news-item">
                    <div class="news-header" onclick="toggleExpand(this)">
                        <div class="news-title">NY Times vs OpenAI: disputa sobre direitos autorais intensifica</div>
                        <div class="news-summary">Documentos judiciais revelam que NY Times acusa OpenAI e Microsoft de usar 10+ mi de artigos (30% do Times) para treinar modelos. Disputa continua na Justiça Federal do Distrito Sul de NY.</div>
                        <div class="expand-indicator">+ Leia mais</div>
                    </div>
                    <div class="news-expanded">
                        <div class="news-full-text">
                            <p>Documentos judiciais revelam que o New York Times acusa OpenAI e Microsoft de ter usado mais de 10 milhões de artigos, incluindo aproximadamente 30% da própria cobertura jornalística do Times, para treinar modelos de inteligência artificial sem autorização prévia. A acusação argumenta que ChatGPT funciona como um substituto direto de conteúdo jornalístico.</p>
                            <p>Executivos internos da OpenAI, segundo os documentos, reconhecem que ChatGPT pode funcionar como um substituto de conteúdo jornalístico. As empresas defendem o uso sob a doutrina de fair use (uso justo), mas a disputa continua em andamento na Justiça Federal do Distrito Sul de Nova York, com implicações significativas para a indústria de mídia e IA.</p>
                        </div>
                        <div class="badges">
                            <span class="badge">NY Times</span>
                            <span class="badge">Poder360</span>
                            <span class="badge">NC News</span>
                        </div>
                        <a href="https://www.nytimes.com" class="source-link">→ Acessar fonte original</a>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p><strong>Newsletter Pessoal</strong> • Agregação de notícias de 18 de setembro de 2026</p>
            <p>Fontes: Folha de S.Paulo, Estadão, G1, InfoMoney, New York Times, Banco Central do Brasil</p>
        </div>
    </div>
    
    <script>
        function switchTab(tabName) {
            // Hide all tabs
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(content => content.classList.remove('active'));
            
            // Remove active class from all buttons
            const buttons = document.querySelectorAll('.tab-button');
            buttons.forEach(button => button.classList.remove('active'));
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to clicked button
            event.target.classList.add('active');
        }
        
        function toggleExpand(element) {
            const expanded = element.nextElementSibling;
            const indicator = element.querySelector('.expand-indicator');
            
            expanded.classList.toggle('show');
            
            if (expanded.classList.contains('show')) {
                indicator.textContent = '− Ler menos';
            } else {
                indicator.textContent = '+ Leia mais';
            }
        }
    </script>
</body>
</html>
```

---

## 4. Funcionalidades JavaScript Explicadas

### `switchTab(tabName)`
- Oculta todas as abas (`.tab-content`)
- Remove classe `active` de todos os botões
- Mostra a aba selecionada
- Adiciona classe `active` ao botão clicado
- Efeito: Filtro por categoria (Finanças, Política, IA)

### `toggleExpand(element)`
- Encontra o elemento `.news-expanded` (irmão do `.news-header`)
- Toggle da classe `show`
- Muda texto do indicador de "Leia mais" para "Ler menos"
- Efeito: Expande/recolhe notícia com contexto adicional

---

## 5. Próximas Etapas (Claude Code)

### 5.1 Automação Diária
- **Script em Python** que:
  1. Busca notícias via WebSearch/APIs (Folha, G1, InfoMoney, etc.)
  2. Identifica URLs específicas de cada matéria
  3. Gera HTML newsletter com código acima
  4. Entrega para Gabriel

### 5.2 Método de Entrega
**Opções a considerar:**
- **Email** (via SMTP ou SendGrid API)
- **Push notification** (se houver app)
- **Webhook** (POST para endpoint)
- **S3/Drive** (salvar arquivo em nuvem)
- **Slack message** (se integrado)

**Preferência inicial:** Email para `lgabrielzp@gmail.com`

### 5.3 Agendamento
- Executar diariamente (horário TBD — sugerir 6-7am horário Brasília)
- Usar `APScheduler` ou `schedule` em Python
- Alternativa: CloudScheduler/Lambda + cron

### 5.4 Estrutura de Dados
```json
{
  "news": [
    {
      "title": "...",
      "summary": "...",
      "full_text": "...",
      "source": "Folha de S.Paulo",
      "url": "https://...",
      "perspective": [
        {
          "source": "Folha",
          "text": "..."
        }
      ],
      "category": "finances|politics|ai"
    }
  ]
}
```

### 5.5 Web Scraping / URL Resolution
- Usar Selenium/Playwright para capturar URLs reais (alguns jornais podem ter paywalls)
- Ou integrar com APIs jornalísticas (NewsAPI, Bing News API)
- Validar URLs antes de incluir no HTML

---

## 6. Arquivo de Configuração (Sugestão)

```python
# newsletter_config.py

NEWSLETTER_CONFIG = {
    "sources": {
        "finanças": [
            "folha.uol.com.br/mercado",
            "infomoney.com.br",
            "bcb.gov.br",
        ],
        "política": [
            "g1.globo.com/politica",
            "jota.info",
            "cartacapital.com.br",
        ],
        "ia": [
            "folha.uol.com.br/tec",
            "cbsnews.com",
            "anthropic.com/research",
        ]
    },
    "schedule": {
        "time": "06:00",  # 6am horário Brasília
        "timezone": "America/Sao_Paulo",
        "frequency": "daily"
    },
    "delivery": {
        "method": "email",
        "recipient": "lgabrielzp@gmail.com",
        "subject": "Newsletter Pessoal - {date}"
    },
    "design": {
        "primary_color": "#c41e3a",
        "background": "#1a1a1a",
        "max_news_per_category": 5
    }
}
```

---

## 7. Resumo Visual do Fluxo

```
[Web Scraping] → [Parse + URL Extract] → [Generate HTML] → [Email/Delivery]
      ↓                    ↓                      ↓
   Daily Run          JSON Structure        newsletter-v2.html     User
   (6am)              (structured)         (com links reais)    (Gabriel)
```

---

## 8. Decisões de Design Importantes

1. **Cores:** Preto (#1a1a1a) + Vermelho (#c41e3a) — inspirado em Folha/FT
2. **Interatividade:** JavaScript puro (sem frameworks) — mantém leve e rápido
3. **Responsividade:** Max-width 900px, padding generoso
4. **Typography:** System fonts (-apple-system, Segoe UI, etc.)
5. **Sem imagens:** Apenas badges e ícones textuais — evita bloqueios de email
6. **Links diretos:** Cada notícia terá URL específica da matéria (não homepage)

---

## 9. Checklist Antes de Passar para Claude Code

- [x] HTML/CSS/JS completo e testado
- [x] Abas funcionando
- [x] Notícias expansíveis funcionando
- [x] Design profissional implementado
- [ ] URLs específicas das notícias coletadas (próximo passo)
- [ ] Automação em Python implementada
- [ ] Teste de email/entrega
- [ ] Agendamento configurado

---

## 10. Referências e Inspirações

- **Folha de S.Paulo:** Design limpo, tipografia clara, uso de vermelho em destaques
- **Financial Times:** Assinatura visual forte, padrão profissional
- **Substack:** Notícias expansíveis, design responsivo
- **Bloomberg:** Badges e categorias claras

---

## Notas Finais

Este documento serve como especificação completa para o Claude Code retomar o projeto. Todas as decisões, iterações e requisitos estão documentados. O próximo passo é implementar:

1. **Script Python** para coleta automática de notícias
2. **Resolução de URLs específicas** (não apenas homepage)
3. **Entrega via email ou outro canal**
4. **Agendamento diário**

Gabriel pode usar este documento para briefar o Claude Code e garantir continuidade sem perder contexto.