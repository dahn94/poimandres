from poimandres.corpus.embeddings import EmbeddingsBackend, FakeEmbeddings


def test_fake_retorna_vetor_por_texto_com_dim_fixa():
    fake = FakeEmbeddings(dim=8)
    vetores = fake.embed(["alfa", "beta", "gama"])
    assert len(vetores) == 3
    assert all(len(v) == 8 for v in vetores)


def test_fake_e_deterministico():
    fake = FakeEmbeddings(dim=8)
    assert fake.embed(["heimarmene"]) == fake.embed(["heimarmene"])


def test_fake_distingue_textos():
    fake = FakeEmbeddings(dim=8)
    assert fake.embed(["nous"]) != fake.embed(["hyle"])


def test_fake_satisfaz_o_protocolo():
    backend: EmbeddingsBackend = FakeEmbeddings()
    assert backend.embed(["x"])
