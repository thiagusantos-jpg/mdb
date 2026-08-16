"""Coletores.

Regra do PRD v2 (§5): coletor não escreve no banco. Ele devolve
`list[OfertaBruta]` e quem persiste é o repositório — o que torna cada coletor
testável sem banco e sem rede.
"""
