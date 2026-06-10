"""Caderno Amigo — 32 requisitos (23 regulares + 9 classe avançada)."""

from app.notebook_catalog.builders import opt_req, req, sec

AMIGO = {
    "slug": "amigo",
    "name": "Amigo",
    "min_age": 10,
    "advanced_title": "Amigo da Natureza",
    "color_hex": "#3b82f6",
    "sections": [
        sec(
            "I",
            "Gerais",
            [
                req(1, "Ter, no mínimo, dez anos de idade."),
                req(2, "Ser membro ativo do Clube de Desbravadores."),
                req(
                    3,
                    "Memorizar e explicar o Voto e a Lei do Desbravador.",
                    "Voto e Lei completos, explicados com suas próprias palavras.",
                ),
                req(4, "Ler o livro do Clube de Leitura Juvenil do ano em curso."),
                req(5, 'Ler o livro "Vaso de barro".'),
                req(6, "Participar ativamente da classe bíblica do seu clube."),
            ],
        ),
        sec(
            "II",
            "Descoberta Espiritual",
            [
                req(
                    1,
                    "Memorizar e demonstrar seu conhecimento",
                    "a) Criação: o que Deus criou em cada dia.\n"
                    "b) 10 Pragas: quais pragas caíram sobre o Egito.\n"
                    "c) 12 Tribos: o nome de cada tribo de Israel.\n"
                    "d) 39 livros do Antigo Testamento e localizar qualquer um na Bíblia.",
                ),
                req(
                    2,
                    "Ler e explicar versos e leitura bíblica",
                    "Versos: João 3:16; Efésios 6:1-3; II Timóteo 3:16; Salmo 1.\n"
                    "Leitura: Gênesis 1–50 (capítulos indicados no cartão) e Êxodo 1–40 (capítulos indicados).",
                ),
            ],
        ),
        sec(
            "III",
            "Servindo a Outros",
            [
                req(
                    1,
                    "Dedicar duas horas servindo a comunidade",
                    "Escolher duas atividades: a) visitar alguém e orar; "
                    "b) oferecer alimento a carente; c) projeto ecológico ou educativo.",
                ),
                req(
                    2,
                    "Redação sobre cidadania",
                    "Escrever redação explicando como ser bom cidadão no lar e na escola.",
                ),
            ],
        ),
        sec(
            "IV",
            "Desenvolvendo Amizade",
            [
                req(
                    1,
                    "Amizade, cidadania e identidade nacional",
                    "Mencionar dez qualidades de um bom amigo; apresentar quatro situações "
                    "em que praticou a Regra Áurea (Mt 7:12); redação sobre bom cidadão; "
                    "cantar o Hino Nacional e conhecer autores da letra e da música.",
                ),
            ],
        ),
        sec(
            "V",
            "Saúde e Aptidão Física",
            [
                opt_req(
                    1,
                    "Completar uma especialidade (escolha única)",
                    "Opções: Natação Principiante I; Cultura física; Nós e amarras; Segurança básica na água.",
                    "amigo_v_especialidade",
                ),
                req(
                    2,
                    "Experiência de Daniel — temperança",
                    "a) Explicar princípios de temperança de Daniel 1 ou participar de encenação.\n"
                    "b) Memorizar e explicar Daniel 1:8.\n"
                    "c) Escrever compromisso pessoal de estilo de vida saudável.",
                ),
                req(
                    3,
                    "Dieta saudável",
                    "Aprender princípios de dieta saudável e ajudar a preparar quadro dos grupos alimentares.",
                ),
            ],
        ),
        sec(
            "VI",
            "Organização e Liderança",
            [
                req(
                    1,
                    "Caminhada de 5 km",
                    "Acompanhar todo o processo de planejamento até a execução de caminhada de 5 km.",
                ),
                req(
                    2,
                    "Organização e liderança complementar",
                    "Participar do planejamento e execução de atividade de unidade com responsabilidade definida.",
                ),
            ],
        ),
        sec(
            "VII",
            "Estudo da Natureza",
            [
                opt_req(
                    1,
                    "Estudo da natureza e acampamento básico",
                    "Completar uma especialidade de natureza (Felinos, Cães, Mamíferos, Sementes ou Aves); "
                    "aprender a purificar água e escrever sobre Jesus como água da vida; "
                    "montar três tipos de barracas.",
                    "amigo_vii_natureza",
                ),
            ],
        ),
        sec(
            "VIII",
            "Arte de Acampar",
            [
                req(
                    1,
                    "Cuidado de cordas e nós práticos",
                    "Demonstrar cuidado com cordas e nós: simples, cego, direito, cirurgião, lais de guia, "
                    "escota, pescador e demais indicados no cartão.",
                ),
                req(2, "Completar a especialidade de Acampamento I."),
                req(
                    3,
                    "Regras de caminhada e quando perdido",
                    "Apresentar 10 regras para caminhada e explicar o que fazer quando estiver perdido.",
                ),
                req(
                    4,
                    "Sinais de pista",
                    "Aprender sinais de pista; preparar e seguir trilha de no mínimo 10 sinais.",
                ),
                req(
                    5,
                    "Segurança em acampamento",
                    "Demonstrar procedimentos de segurança em fogueira e área de acampamento.",
                ),
            ],
        ),
        sec(
            "IX",
            "Estilo de Vida",
            [
                req(
                    1,
                    "Especialidade em Artes e Habilidades Manuais",
                    "Completar uma especialidade na área de Artes e Habilidades Manuais.",
                ),
            ],
        ),
        sec(
            "AV",
            "Classe Avançada — Amigo da Natureza",
            [
                req(1, "Memorizar, cantar ou tocar o Hino dos Desbravadores e conhecer sua história."),
                opt_req(
                    2,
                    "Personagem do Antigo Testamento",
                    "Escolher José, Jonas, Ester ou Rute e conversar com o grupo sobre o cuidado de Deus.",
                    "amigo_av_personagem",
                ),
                req(3, "Levar pelo menos dois amigos não adventistas à Escola Sabatina ou ao clube."),
                req(
                    4,
                    "Higiene e boas maneiras",
                    "Conhecer princípios de higiene e boas maneiras à mesa; comportamento com diferentes idades.",
                ),
                req(5, "Completar a especialidade de Arte de acampar."),
                req(
                    6,
                    "Flores e insetos da região",
                    "Conhecer e identificar 10 flores silvestres e 10 insetos da sua região.",
                ),
                req(7, "Iniciar fogueira com um fósforo usando materiais naturais."),
                req(
                    8,
                    "Uso seguro de faca, facão ou machadinha",
                    "Usar corretamente e conhecer dez regras de segurança.",
                ),
                opt_req(
                    9,
                    "Especialidade avançada (escolha única)",
                    "Atividades missionárias e comunitárias OU Atividades agrícolas e afins.",
                    "amigo_av_especialidade",
                ),
            ],
            advanced=True,
        ),
    ],
}
