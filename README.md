# Local Food — Grupo 10 — Entrega preliminar

Thifany Antoni — 16077  
Pedro Perez — 18623  
Entrega: 31/10/2026

## Abrir no Visual Studio Code

1. Extrair o ZIP por completo; não executar ficheiros dentro do ZIP.
2. Abrir a pasta `projeto01_grupo10` no VS Code.
3. No terminal, instalar as dependências no Python que vão usar:

```sh
python -m pip install -r requirements.txt
```

4. Ter as extensões Python e Jupyter do VS Code disponíveis.
5. Abrir `notebooks/02_eda_tiny.ipynb`, selecionar esse ambiente Python no seletor de kernel e clicar em **Run All / Executar Tudo**.
6. Abrir `notebooks/01_Project01_G10.ipynb` e executar tudo.

Os notebooks também podem ser abertos no Jupyter. Os caminhos são relativos à pasta do projeto ou à pasta `notebooks`, sem caminhos específicos de um computador.

## Conteúdo

- `data_tiny/`, `data_small/`: CSV originais do docente, sem alterações.
- `src/model.py`: classes, leitura, custo e verificação de planos.
- `src/analysis.py`: verificações de integridade e viabilidade individual.
- `notebooks/02_eda_tiny.ipynb`: análise exploratória com tabelas e gráficos.
- `notebooks/01_Project01_G10.ipynb`: introdução, modelação, demonstração e conclusão preliminar.
- `tests/test_model.py`: testes de regras e exemplos inválidos.

## Executar os testes

Na pasta principal:

```sh
python -m unittest discover -s tests -v
```

## Limites desta entrega

Não inclui Greedy, A*, Hill Climbing ou CSP. O modelo verifica planos fornecidos; não os otimiza. A rota de demonstração transporta apenas um item. `require_all=False` serve para demonstrações parciais, enquanto o comportamento por defeito exige todos os itens.

O custo mede km, não euros. Todas as hipóteses estão documentadas no notebook principal, incluindo a possibilidade de separar linhas de uma encomenda, o regresso ao armazém e o tratamento de operações simultâneas. Não se deduz necessidade de refrigeração a partir da categoria do produto.

O grupo deve ler, compreender e rever o código antes da defesa. Foi utilizado apoio de IA na preparação; respeitar as orientações da unidade curricular quanto à declaração desse apoio.

## Entrega

Carregar a pasta completa num repositório GitHub e dar acesso ao docente, como indicado no enunciado. Entregar no Moodle um ZIP com todos os ficheiros necessários. Este pacote não foi publicado nem submetido automaticamente.
