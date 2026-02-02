import numpy as np
import geopandas as gpd
import pandas as pd
import json
from scipy.stats import binom


geopackage = r"NAVN PÅ DIN GEOPACKAGE FIL HER"
veg = gpd.read_file(geopackage, layer="FMO_2felts_dekkebredde_u_atk_midtrekkverk_motorveg_med_ulykker").to_crs(25833)

fylker = {
  3: "Oslo",
  11: "Rogaland",
  15: "Møre og Romsdal",
  18: "Nordland",
  31: "Østfold",
  32: "Akershus",
  33: "Buskerud",
  34: "Innlandet",
  39: "Vestfold",
  40: "Telemark",
  42: "Agder",
  46: "Vestland",
  50: "Trøndelag",
  55: "Troms",
  56: "Finnmark"
}

class Normale_ulykker:
    """
    Beregner forventet (normalt) antall trafikkulykker for en vegstrekning
    basert på en generalisert lineær modell (Poisson / NB), med justering
    for trafikkmengde, vegstandard, omgivelser og tidsutvikling.

    Klassen brukes som grunnlag for:
    - Empirisk Bayes-estimering
    - Før–etter-analyser
    - Sammenlikning av observerte og forventede ulykker
    """

    def __init__(self, lengde, aar, antall_aar, ulykkestype, adt, adt_aar, fart, kjorefelt, krysstype,vegtype, midtdeler, fmo, atk, belysning, fylke):
        self.ulykkestype = ulykkestype
        self.fart = fart
        self.kjorefelt = kjorefelt
        self.krysstype = krysstype
        self.vegtype = vegtype
        self.midtdeler = midtdeler
        self.fmo = fmo
        self.atk = atk
        self.belysning = belysning
        self.fylke = fylke
        self.lengde = lengde
        self.antall_aar = antall_aar   
        self.aar = aar
        self.adt = adt * self.ADT_vekst(adt_aar)  

        self.antall_predikerte = np.exp(self.adt_koeff() + self.fart_koeff() + self.kjorefelt_koeff() + self.krysstype_koeff() + self.vegtype_koeff() + self.midtdeler_koeff() + self.fmo_koeff() + self.akt_koeff() + self.belysning_koeff() + self.fylke_koeff() + self.konstantterm() + self.lengdeaar_koeff())

        self.antall_normale = self.antall_predikerte * self.finn_trend()

        self.overspredning_psu = np.exp(np.log(self.lengde)*0.653 + np.log(self.antall_aar)*0.086 + np.log(self.adt)*0.375 - 6.650)
        self.overspredning_dr = np.exp(np.log(self.lengde)*1.509 + np.log(self.antall_aar)*1.575 + np.log(self.adt)*0.848 - 21.672) 
        self.overspredning_hs = np.exp(np.log(self.lengde)*1.509 + np.log(self.antall_aar)*1.575 + np.log(self.adt)*0.848 - 11.024) 


    def adt_koeff(self):
        if self.ulykkestype == "psu":
            return np.log(self.adt) * 0.874

        if self.ulykkestype == "dr/hs":
            return np.log(self.adt) * 0.814

    def fart_koeff(self):
        if self.ulykkestype == "psu":
            if self.fart == 30:
                return 0.213
            elif self.fart == 40:
                return 0.181
            elif self.fart == 50:
                return 0.112
            elif self.fart == 60:
                return -0.032
            elif self.fart == 70:
                return -0.101
            elif self.fart == 80:
                return 0.0
            elif self.fart == 90:
                return -0.211
            elif self.fart == 100:
                return -0.685
            elif self.fart == 110:
                return -0.829
            
        if self.ulykkestype == "dr/hs":
            if self.fart == 30:
                return -0.237
            elif self.fart == 40:
                return -0.027
            elif self.fart == 50:
                return -0.134
            elif self.fart == 60:
                return -0.314
            elif self.fart == 70:
                return -0.230
            elif self.fart == 80:
                return 0.0
            elif self.fart == 90:
                return -0.066
            elif self.fart == 100:
                return -0.278
            elif self.fart == 110:
                return -0.278
        
    def kjorefelt_koeff(self):
        if self.ulykkestype == "psu":
            if self.kjorefelt == 2:
                return 0.0
            elif self.kjorefelt == 3:
                return 0.073
            elif self.kjorefelt == 4:
                return 0.298
            elif self.kjorefelt == 5:
                return 0.517
            elif self.kjorefelt > 5:
                return 0.675
    
        if self.ulykkestype == "dr/hs":
            if self.kjorefelt == 2:
                return 0.0
            elif self.kjorefelt == 3:
                return -0.500
            elif self.kjorefelt == 4:
                return 0.231
            elif self.kjorefelt == 5:
                return 0.001
            elif self.kjorefelt > 5:
                return 0.001

    def krysstype_koeff(self):
        if self.ulykkestype == "psu":
            if self.krysstype == "x-kryss":
                return 0.416
            elif self.krysstype == "t-kryss":
                return 0.147
            elif self.krysstype == "rundkjoring":
                return 0.035
            elif self.krysstype == "rampe":
                return 0.300
            else:
                return 0.0
            
        if self.ulykkestype == "dr/hs":
            if self.krysstype == "x-kryss":
                return 0.433
            elif self.krysstype == "t-kryss":
                return 0.073
            elif self.krysstype == "rundkjoring":
                return -0.146
            elif self.krysstype == "rampe":
                return 0.070
            else:
                return 0.0
            
    def vegtype_koeff(self):
        if self.ulykkestype == "psu":
            if self.vegtype == "motorveg":
                return -0.288
            elif self.vegtype == "tofelts planskilt":
                return -0.405
            elif self.vegtype == "øvrig ten-t":
                return -0.035
            elif self.vegtype == "øvrig ev/rv" or self.vegtype == "E" or self.vegtype == "R":
                return -0.012
            elif self.vegtype == "fylkesveg" or self.vegtype == "F":
                return 0.0
            
        if self.ulykkestype == "dr/hs":
            if self.vegtype == "motorveg":
                return -0.373
            elif self.vegtype == "tofelts plansksilt":
                return -0.497
            elif self.vegtype == "øverig ten-t":
                return 0.192
            elif self.vegtype == "øverig ev/rv" or self.vegtype == "E" or self.vegtype == "R":
                return 0.116
            elif self.vegtype == "fylkesveg" or self.vegtype == "F":
                return 0.0
    
    def midtdeler_koeff(self):
        if self.ulykkestype == "psu":
            if self.midtdeler == "ingen":
                return 0.0
            elif self.midtdeler == "kun midtdeler":
                return -0.056
            elif self.midtdeler == "kun midtrekkverk":
                return -0.520
            elif self.midtdeler == "begge":
                return -0.634
            
        if self.ulykkestype == "dr/hs":
            if self.midtdeler == "ingen":
                return 0.0
            elif self.midtdeler == "kun midtdeler":
                return 0.031
            elif self.midtdeler == "kun midtrekkverk":
                return -1.093
            elif self.midtdeler == "begge":
                return -1.077
    
    def fmo_koeff(self):
        if self.ulykkestype == "psu":
            if self.fmo == "ja":
                return -0.427
            else:
                return 0.0
            
        if self.ulykkestype == "dr/hs":
            if self.fmo == "ja":
                return -0.355
            else:
                return 0.0

    def akt_koeff(self):
        if self.ulykkestype == "psu":
            if self.atk == "sakt":
                return -0.427
            elif self.atk == "pakt":
                return 0.111
            else:
                return 0.0
        
        if self.ulykkestype == "dr/hs":
            if self.atk == "sakt":
                return -0.093
            elif self.atk == "pakt":
                return 0.007
            else:
                return 0.0

    def belysning_koeff(self):
        if self.ulykkestype == "psu":
            if self.belysning == "ja":
                return 0.033
            else:
                return 0.0
            
        if self.ulykkestype == "dr/hs":
            if self.belysning == "ja":
                return -0.022
            else:
                return 0.0
    
    def fylke_koeff(self):
        if self.ulykkestype == "psu":
            if self.fylke == "Østfold":
                return 0.337
            elif self.fylke == "Akershus":
                return 0.071
            elif self.fylke == "Oslo":
                return 0.166
            elif self.fylke == "Hedemark":
                return -0.137
            elif self.fylke == "Oppland":
                return 0.155
            elif self.fylke == "Innlandet":
                return (-0.137+0.155)/2
            elif self.fylke == "Buskerud":
                return -0.108
            elif self.fylke == "Vestfold":
                return 0.233
            elif self.fylke == "Telemark":
                return 0.324
            elif self.fylke == "Aust-Agder":
                return 0.161
            elif self.fylke == "Vest-Agder":
                return 0.012
            elif self.fylke == "Agder":
                return (0.161+0.012)/2
            elif self.fylke == "Rogaland":
                return 0.0
            elif self.fylke == "Hordaland":
                return 0.287
            elif self.fylke == "Sogn og Fjorlandet":
                return 0.154
            elif self.fylke == "Vestland":
                return (0.287 + 0.154)/2
            elif self.fylke == "Møre og Romsdal":
                return 0.111
            elif self.fylke == "Trøndelag":
                return -0.107
            elif self.fylke == "Nordland":
                return -0.077
            elif self.fylke == "Troms":
                return -0.319
            elif self.fylke == "Finnmark":
                return -0.175
        
        if self.ulykkestype == "dr/hs":
            if self.fylke == "Østfold":
                return 0.064
            elif self.fylke == "Akershus":
                return 0.198
            elif self.fylke == "Oslo":
                return 0.078
            elif self.fylke == "Hedemark":
                return 0.040
            elif self.fylke == "Oppland":
                return 0.367
            elif self.fylke == "Innlandet":
                return np.log(np.exp(0.367)+np.exp(0.040)/2)
            elif self.fylke == "Buskerud":
                return 0.065
            elif self.fylke == "Vestfold":
                return 0.247
            elif self.fylke == "Telemark":
                return 0.195
            elif self.fylke == "Aust-Agder":
                return -0.252
            elif self.fylke == "Vest-Agder":
                return 0.084
            elif self.fylke == "Agder":
                return (0.195-0.252)/2
            elif self.fylke == "Rogaland":
                return 0.0
            elif self.fylke == "Hordaland":
                return 0.231
            elif self.fylke == "Sogn og Fjorlandet":
                return -0.064
            elif self.fylke == "Vestland":
                return (-0.064 + 0.231)/2
            elif self.fylke == "Møre og Romsdal":
                return 0.036
            elif self.fylke == "Trøndelag":
                return -0.180
            elif self.fylke == "Nordland":
                return -0.030
            elif self.fylke == "Troms":
                return -0.305
            elif self.fylke == "Finnmark":
                return -0.173

    def lengdeaar_koeff(self):
        return np.log(self.lengde * self.antall_aar)

    def konstantterm(self):
        if self.ulykkestype == "psu":
            return -16.436

        if self.ulykkestype == "dr/hs":
            return -17.398

    def finn_trend(self):
        trend_array_psu = [2.6056,
                        2.4785,
                        2.3577,
                        2.2427,
                        2.1333,
                        2.0292,
                        1.9303,
                        1.8361,
                        1.7466,
                        1.6614,
                        1.5804,
                        1.5033,
                        1.4300,
                        1.3602,
                        1.2939,
                        1.2308,
                        1.1708,
                        1.1137,
                        1.0000,
                        1.0077,
                        0.9585,
                        0.9118,
                        0.8673,
                        0.8250,
                        0.7848,
                        0.7465,
                        0.7101,
                        0.6755,
                        0.6425,
                        0.6112,
                        0.5814,
                        0.5530,
                        0.5261,
                        0.5004,
                        0.4760,
                        0.4528,
                        0.4307,
                        0.4097,
                        0.3897,
                        0.3707,
                        0.3526]
        
        trend_array_dr_hs = [2.0763,
                            1.9969,
                            1.9205,
                            1.8471,
                            1.7764,
                            1.7085,
                            1.6431,
                            1.5803,
                            1.5198,
                            1.4617,
                            1.4058,
                            1.3520,
                            1.3003,
                            1.2506,
                            1.2027,
                            1.1567,
                            1.1125,
                            1.0699,
                            1.0000,
                            0.9897,
                            0.9518,
                            0.9154,
                            0.8804,
                            0.8467,
                            0.8143,
                            0.7832,
                            0.7532,
                            0.7244,
                            0.6967,
                            0.6701,
                            0.6444,
                            0.6198,
                            0.5961,
                            0.5733,
                            0.5513,
                            0.5303,
                            0.5100,
                            0.4905,
                            0.4717,
                            0.4537,
                            0.4363
                            ]
        if self.ulykkestype == "psu":
            return trend_array_psu[int(self.aar - 2000)]
        if self.ulykkestype == "dr/hs":
            return trend_array_dr_hs[int(self.aar - 2000)]

    def ADT_vekst(self, adt_aar):
        
        kumulativ_fylkesvegar_2010_2024 = [
            100.0,    # 2010
            101.0,    # 2011
            102.2,    # 2012
            103.2,    # 2013
            105.0,    # 2014
            106.5,    # 2015
            107.1,    # 2016
            108.2,    # 2017
            108.1,    # 2018
            107.8,    # 2019
            102.8,    # 2020
            106.0,    # 2021
            107.7,    # 2022
            108.5,    # 2023
            109.2     # 2024
        ]
        kumulativ_europa_riksvegar_2010_2024 = [
            100.0,    # 2010
            101.5,    # 2011
            103.2,    # 2012
            104.6,    # 2013
            106.3,    # 2014
            108.8,    # 2015
            109.4,    # 2016
            110.9,    # 2017
            111.3,    # 2018
            112.0,    # 2019
            103.7,    # 2020
            107.9,    # 2021
            113.6,    # 2022
            114.5,    # 2023
            115.3     # 2024
        ]

        kumulativ_lette_kjoretoy_1998_2024 = [
            100.0,    # 1998
            101.9,    # 1999
            103.6,    # 2000
            106.1,    # 2001
            109.2,    # 2002
            111.1,    # 2003
            113.1,    # 2004
            115.8,    # 2005
            117.4,    # 2006
            120.6,    # 2007
            122.1,    # 2008
            123.3,    # 2009
            124.6,    # 2010
            126.2,    # 2011
            128.3,    # 2012
            129.9,    # 2013
            132.1,    # 2014
            134.5,    # 2015
            134.7,    # 2016
            135.9,    # 2017
            135.9,    # 2018
            136.2,    # 2019
            127.2,    # 2020
            131.9,    # 2021
            137.1,    # 2022
            138.7,    # 2023
            139.7     # 2024
        ]
        min_aar = 2010
        if self.aar < 2010:
            ADT_trend = kumulativ_lette_kjoretoy_1998_2024.copy()
            min_aar = 1998
        elif self.vegtype == "E" or self.vegtype == "R":
            ADT_trend = kumulativ_europa_riksvegar_2010_2024.copy()
        else:
            ADT_trend = kumulativ_fylkesvegar_2010_2024.copy()
        return ADT_trend[int(min(self.aar,2024) - min_aar)] / ADT_trend[int(min(adt_aar,2024) - min_aar)]

def hauer_poisson_test(
    X: int,
    Y: int,
    t_x: float,
    t_y: float,
    k0: float,
    alpha: float = 0.05
):
    """
    Parameters
    ----------
    X : int
        Antall ulykker etter tiltak
    Y : int
        Antall ulykker før tiltak
    t_x : float
        tidsperiode etter
    t_y : float
        tidsperiode før
    k0 : float
        Antatt ulykkestrend uavhening av tiltak
    alpha : float
        Signifikansnivå
    """
    n = X + Y

    u0 = (k0 * t_x) / (k0 * t_x + t_y)

    p_value = binom.cdf(X, n, u0)

    return {
        "X": X,
        "Y": Y,
        "t_x": t_x,
        "t_y": t_y,
        "k0": k0,
        "u0": u0,
        "n": n,
        "expected_X_under_H0": n * u0,
        "p_value": p_value,
        "alpha": alpha,
        "reject_H0": p_value < alpha
    }


def hauer_rejection_threshold(n, u0, alpha):
    """
    Finner X* slik at P(X <= X* | H0) <= alpha
    """
    for x_star in range(n + 1):
        if binom.cdf(x_star, n, u0) > alpha:
            return x_star - 1
    return n



def hauer_power(
    X: int,
    Y: int,
    t_x: float,
    t_y: float,
    k0: float,
    kA: float,
    alpha: float = 0.05
):
    n = X + Y

    u0 = (k0 * t_x) / (k0 * t_x + t_y)

    uA = (kA * k0 * t_x) / (kA * k0 * t_x + t_y)

    x_star = hauer_rejection_threshold(n, u0, alpha)

    power = binom.cdf(x_star, n, uA)

    return {
        "n": n,
        "kA": kA,
        "u0": u0,
        "uA": uA,
        "x_star": x_star,
        "alpha": alpha,
        "power": power
    }

def beregn_antall_normale(veg, ulykkestype = "psu", periode = "Etter", vegbredde_min = 7.0, vegbredde_maks = 7.5, tidsperiode = 4, ekskluder_lett_skadde = False):
    mu_total = 0
    var_total = 0
    total_lengde = 0
    antall_forventet = 0
    totalt_antall_normal = 0
    totalt_antall_reg_ulykker = 0 
    vekta_adt = 0
    ulykkes_aar_histogram = {}
    for _, row in veg.iterrows():
        etableringsår = row["Etableringsår"]
        if pd.isna(row["ÅDT, total"]) or row["ÅDT, total"] <= 0 or pd.isna(etableringsår) or pd.isna(row["Fartsgrense"]) or pd.isna(row["vegkategori"]):
            continue
        if row["Dekkebredde"] > vegbredde_maks or row["Dekkebredde"] < vegbredde_min or etableringsår > 2025 - tidsperiode:
            continue
        normale = Normale_ulykker(
            lengde=row.geometry.length,
            aar=etableringsår + tidsperiode // 2 * (1 if periode == "Etter" else -1),
            antall_aar=tidsperiode,                 
            ulykkestype=ulykkestype,
            adt=row["ÅDT, total"],
            adt_aar=row["År, gjelder for"],
            fart=row["Fartsgrense"],
            kjorefelt=2,
            krysstype=None,
            vegtype=row["vegkategori"],
            midtdeler="ingen",
            fmo="nei",
            atk=None,
            belysning=None,
            fylke=fylker[row["fylke"]]
        )
        total_lengde += row.geometry.length
        mu_i = normale.antall_predikerte
        phi_i = normale.overspredning_psu
        var_i = mu_i + mu_i**2 / phi_i

        mu_total += mu_i
        totalt_antall_normal += normale.antall_normale
        var_total += var_i
        eb_vekt = 1/(1+(mu_i/phi_i))

        antall_registrete_ulykker = 0
        ulykker_år_etter_etableringsår = row["ulykker_meta"]

        if row["ulykker_meta"] and row["ulykker_meta"] != "":
            ulykker_år_etter_etableringsår = json.loads(row["ulykker_meta"])

            for ulykke in ulykker_år_etter_etableringsår:

                if ekskluder_lett_skadde and ulykke["alvorlighetsgrad"] == "lettere skadde":
                    continue

                aar = int(ulykke["aar_etter_etablering_FMO"])
                if periode == "Etter":
                    if aar > 0 and aar <= tidsperiode:
                        antall_registrete_ulykker += 1
                        ulykkes_aar_histogram[etableringsår + ulykke["aar_etter_etablering_FMO"]] = ulykkes_aar_histogram.get(etableringsår + ulykke["aar_etter_etablering_FMO"], 0) + 1

                else:
                    if aar < 0 and aar >= -tidsperiode:
                        antall_registrete_ulykker += 1
                        ulykkes_aar_histogram[etableringsår + ulykke["aar_etter_etablering_FMO"]] = ulykkes_aar_histogram.get(etableringsår + ulykke["aar_etter_etablering_FMO"], 0) + 1


        totalt_antall_reg_ulykker += antall_registrete_ulykker
        antall_forventet += eb_vekt * normale.antall_normale + (1 - eb_vekt) * antall_registrete_ulykker
        
        vekta_adt += normale.adt * row.geometry.length

    phi_effektiv = mu_total**2 / (var_total - mu_total)
    return totalt_antall_normal, phi_effektiv, antall_forventet, total_lengde, totalt_antall_reg_ulykker, vekta_adt / total_lengde, ulykkes_aar_histogram


def analyser_ulykker(
    veg,
    ulykkestype,
    vegbredde_min,
    vegbredde_maks,
    tidsperiode,
    label=""
):
    beregnet_for, overspredning_for, antall_forventet_for, total_lengde, reg_for, adt_for, ulykkes_aar_histogram_for = beregn_antall_normale(
        veg,
        ulykkestype=ulykkestype,
        periode="Før",
        vegbredde_min=vegbredde_min,
        vegbredde_maks=vegbredde_maks,
        tidsperiode=tidsperiode,
        ekskluder_lett_skadde=(ulykkestype == "dr/hs")
    )

    beregnet_etter, overspredning_etter, antall_forventet_etter, total_lengde, reg_etter, adt_etter, ulykkes_aar_histogram_etter = beregn_antall_normale(
        veg,
        ulykkestype=ulykkestype,
        periode="Etter",
        vegbredde_min=vegbredde_min,
        vegbredde_maks=vegbredde_maks,
        tidsperiode=tidsperiode,
        ekskluder_lett_skadde=(ulykkestype == "dr/hs")
    )
    eb_vekt_for = 1/(1+(beregnet_for/overspredning_for))

    forventet_for = eb_vekt_for * beregnet_for + (1 - eb_vekt_for) * reg_for
    forventet = forventet_for * (beregnet_etter / beregnet_for)
    avvik = reg_etter - forventet
    prosent = avvik / forventet if forventet > 0 else float("nan")
    prosent_effekt = ((reg_etter - reg_for) / reg_for)
    
    hauer = hauer_poisson_test(
        X=reg_etter,
        Y=reg_for,
        t_x=1,
        t_y=1,
        k0=adt_etter / adt_for,
        alpha=0.05
    )

    power_30 = hauer_power(
        X=reg_etter,
        Y=reg_for,
        t_x=tidsperiode,
        t_y=tidsperiode,
        k0=adt_etter / adt_for,
        kA=0.7,   # 30 % reduksjon
    )["power"]

    hauer_EB = hauer_poisson_test(
        X=reg_etter,
        Y=int(forventet),
        t_x=1,
        t_y=1,
        k0=adt_etter / adt_for,
        alpha=0.05
    )

    power_30_EB = hauer_power(
        X=reg_etter,
        Y=int(forventet),
        t_x=1,
        t_y=1,
        k0=adt_etter / adt_for,
        kA=0.7,   # 30 % reduksjon
    )["power"]

    print("\n" + "=" * 50)
    print(f"Ulykkesanalyse: {label}")
    print(f"Ulykkestype: {ulykkestype}")
    print(f"Analyseperiode: {tidsperiode} år før / {tidsperiode} år etter")
    print(f"Total analysert veglengde: {total_lengde/1000:.2f} km")
    print("=" * 50)

    # --------------------------------------------------
    # 1. OBSERVERTE DATA (FAKTA)
    # --------------------------------------------------
    print("\n1) Observerte ulykker (rå data)")
    print("-" * 50)
    print(f"Antall ulykker før tiltak:  {reg_for}")
    print(f"Antall ulykker etter tiltak:{reg_etter}")
    print(f"Observerte endring:         {prosent_effekt:+.1%}")
    print("Dette er den faktiske endringen i registrerte ulykker.\n")

    # --------------------------------------------------
    # 2. JUSTERT FOR TRAFIKK (ENKEL KORREKSJON)
    # --------------------------------------------------
    print("2) Justering for endret trafikkmengde")
    print("-" * 50)
    print(f"ÅDT før tiltak:   {adt_for:.0f}")
    print(f"ÅDT etter tiltak: {adt_etter:.0f}")

    reg_etter_trafikkjustert = reg_etter * (adt_for / adt_etter)
    prosent_trafikkjustert = (reg_etter_trafikkjustert - reg_for) / reg_for

    print(f"Ulykker etter (trafikkjustert): {reg_etter_trafikkjustert:.1f}")
    print(f"Endring etter trafikkjustering: {prosent_trafikkjustert:+.1%}")
    print(
        "Denne justeringen viser hva ulykkestallet etter tiltak ville vært\n"
        "dersom trafikkmengden var den samme som før.\n"
    )

    # --------------------------------------------------
    # 3. STATISTISK TEST (HAUER)
    # --------------------------------------------------
    print("3) Statistisk test (Hauer – eksakt Poisson)")
    print("-" * 50)
    print(f"p-verdi: {hauer['p_value']:.4f}")
    print(f"Signifikant ved 5 % nivå: {'Ja' if hauer['reject_H0'] else 'Nei'}")

    if hauer["reject_H0"]:
        print(
            "Tolkning:\n"
            "Det er svært lite sannsynlig at den observerte reduksjonen\n"
            "skyldes tilfeldigheter alene."
        )
    else:
        print(
            "Tolkning:\n"
            "Dataene gir ikke tilstrekkelig grunnlag for å si at tiltaket\n"
            "har hatt en sikkerhetseffekt."
        )

    # --------------------------------------------------
    # 4. POWER (HYPOTETISK SCENARIO)
    # --------------------------------------------------
    print("\n4) Teststyrke (power – hypotetisk vurdering)")
    print("-" * 50)
    print(
        f"Hvis den sanne effekten var en 30 % reduksjon i ulykker,\n"
        f"ville denne analysen hatt {power_30:.1%} sannsynlighet\n"
        f"for å påvise effekten som statistisk signifikant."
    )
    print(
        "Merk:\n"
        "Dette sier ingenting om hvor stor effekten faktisk er,\n"
        "kun hvor følsom analysen er.\n"
    )

    # --------------------------------------------------
    # 3. STATISTISK TEST (HAUER) EB
    # --------------------------------------------------
    print("3) Statistisk test EB (Hauer – eksakt Poisson)")
    print("-" * 50)
    print(f"p-verdi: {hauer_EB['p_value']:.4f}")
    print(f"Signifikant ved 5 % nivå: {'Ja' if hauer_EB['reject_H0'] else 'Nei'}")

    if hauer_EB["reject_H0"]:
        print(
            "Tolkning:\n"
            "Det er svært lite sannsynlig at den observerte reduksjonen\n"
            "skyldes tilfeldigheter alene."
        )
    else:
        print(
            "Tolkning:\n"
            "Dataene gir ikke tilstrekkelig grunnlag for å si at tiltaket\n"
            "har hatt en sikkerhetseffekt."
        )

    # --------------------------------------------------
    # 4. POWER (HYPOTETISK SCENARIO) EB
    # --------------------------------------------------
    print("\n4) Teststyrke EB (power – hypotetisk vurdering)")
    print("-" * 50)
    print(
        f"Hvis den sanne effekten var en 30 % reduksjon i ulykker,\n"
        f"ville denne analysen hatt {power_30_EB:.1%} sannsynlighet\n"
        f"for å påvise effekten som statistisk signifikant."
    )
    print(
        "Merk:\n"
        "Dette sier ingenting om hvor stor effekten faktisk er,\n"
        "kun hvor følsom analysen er.\n"
    )

    # --------------------------------------------------
    # 5. MODELLBASERT FORVENTNING (Empirisk Bayes)
    # --------------------------------------------------
    print("5) Modellbasert forventning (Empirisk Bayes)")
    print("-" * 50)
    print(f"Normalmodell – forventet ulykker før:  {beregnet_for:.1f}")
    print(f"Normalmodell – forventet ulykker etter:  {beregnet_etter:.1f}")
    print(f"Overspredning:                          {overspredning_for:.1f}")
    print(f"EB-vekt:                               {eb_vekt_for:.2f}")

    print(f"\nEB-estimert forventning etter tiltak:  {forventet:.1f}")
    print(f"Faktisk observerte etter:              {reg_etter}")
    print(f"Avvik fra EB-forventning:              {avvik:+.1f} ({prosent:+.1%})")


    print("=" * 50)


def filtrer_pa_dekkebredde(veg, min_bredde, maks_bredde):
    """
    Returnerer veger med dekkebredde innenfor [min_bredde, maks_bredde].
    """
    return veg[
        veg["Dekkebredde"].notna() &
        (veg["Dekkebredde"] >= min_bredde) &
        (veg["Dekkebredde"] <= maks_bredde)
    ].copy()



tidsperiode = 4
veg = veg[veg["Fartsgrense"].isin((60, 70,80))].copy()
for ulykkestype in ["dr/hs", "psu"]:
    analyser_ulykker(
        veg,
        ulykkestype,
        vegbredde_min=0.0,
        vegbredde_maks=100.0,
        tidsperiode=tidsperiode,
        label="Alle vegbredder"
    )


for ulykkestype in ["dr/hs", "psu"]:
    analyser_ulykker(
        veg,
        ulykkestype,
        vegbredde_min=7.0,
        vegbredde_maks=7.5,
        tidsperiode=tidsperiode,
        label="Vegbredde 7.0–7.5 m"
    )
