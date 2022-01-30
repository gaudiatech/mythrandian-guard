import math
import random
from math import floor

from game_defs import LackeyCodes, MAX_MANA_PTS, BASE_LIMIT_LACKEYS
from game_defs import create_artifact_storage, ArtifactCodes, ArtifactNames
from game_events import MyEvTypes
from pkatagames_sdk.capsule.struct.misc import enum_builder_nplus
from pkatagames_sdk.engine import CogObject


FULL_LIFE_SYM = -399601
MAX_FOCUS = 20
MAX_LEVEL = 90

PrimaryStats = enum_builder_nplus(
    0,
    'Endurance',
    'Strength',
    'Perception',
    'Sadism',
    'Willpower',
)

SecondaryStats = enum_builder_nplus(
    PrimaryStats.last_code + 1,
    'MaxHp',
    'BaseDmg',
    'ArmorClass',
    'LifeSteal',
    'PowerIncrem',
)


class StatsFramework:

    def __init__(self):
        self.LVL_TO_XPT, self.XPT_TO_LVL = dict(), dict()

        cst = 250
        self.LVL_TO_XPT[1] = 0
        self.LVL_TO_XPT[2] = cst
        for k in range(3, MAX_LEVEL + 1):
            self.LVL_TO_XPT[k] = self.LVL_TO_XPT[k - 1] + cst * (k - 1)

        # mirror the information, in case its useful
        for level, xp_req in self.LVL_TO_XPT.items():
            self.XPT_TO_LVL[xp_req] = level

    def get_max_level(self):
        return MAX_LEVEL

    def calc_level(self, montant_xp):
        paliers_ord = list(self.XPT_TO_LVL.keys())
        paliers_ord.sort()
        paliers_ord.reverse()  # higher level to lower level
        for thresh in paliers_ord:
            if montant_xp >= thresh:
                return self.XPT_TO_LVL[thresh]


class StatsKern:
    """
    modélise les statistiques de combat d'un personnage
    - contient l'info. de niveau & calcule tous les bonus liés au niveau
    - contient l'info. de stats bonus reçues de l'extérieur
    """

    def __init__(self, curr_hp: int, xp_amount: int, bonus_eq: dict):
        # game balancing
        self.__max_focus = 16
        self.armor_class_cap, self.lifesteal_cap, self.hp_per_en = 0.35, 0.4, 10
        self.en_per_thr, self.st_per_thr, self.pe_per_thr, self.sa_per_thr, self.wp_per_thr = 3, 5, 2, 2, 2
        self.alpha, self.beta, self.gamma = 1, 1, 1

        # self.ev_st_change = CgmEvent(MyEvTypes.StatsChange, local_av=local_av)
        self.base_stats = dict()
        self.effectiv_stats = None
        self.__curr_focus = 0
        self.__curr_xp = xp_amount
        self.bonus_eq = None
        self.__level = None
        level_adhoc = StatsFramework().calc_level(xp_amount)
        self.__impacte_stats(level_adhoc, bonus_eq)

        if curr_hp == FULL_LIFE_SYM:
            self.__curr_hp = self._det_stat_secondaire(SecondaryStats.MaxHp)
        else:
            self.__curr_hp = curr_hp

    def det_ratio_for_levelup(self):
        """
        :return: un flotant compris entre 0 et 1, à deux chiffres significatifs
        """
        fram = StatsFramework()
        borne_inf = fram.LVL_TO_XPT[self.__level]
        borne_sup = fram.LVL_TO_XPT[self.__level + 1]
        if borne_sup is None:
            tmp = 0
        else:
            q = self.__curr_xp - borne_inf
            res = q / (borne_sup - borne_inf)
            tmp = math.floor(res * 100)
        return tmp / 100  # two decimals

    def __impacte_stats(self, nouveau_level, nouveau_bonus_eq):
        self.__level = nouveau_level

        # --- calcul des stats de base
        for st_code in PrimaryStats.all_codes:
            self.base_stats[st_code] = 1

        # bonus identique attribué à chaque dépassement de palier
        self.base_stats[PrimaryStats.Endurance] += self.en_per_thr
        self.base_stats[PrimaryStats.Strength] += self.st_per_thr
        self.base_stats[PrimaryStats.Perception] += self.pe_per_thr
        self.base_stats[PrimaryStats.Sadism] += self.sa_per_thr
        self.base_stats[PrimaryStats.Willpower] += self.wp_per_thr

        self.set_bonus_eq(nouveau_bonus_eq)

    def set_bonus_eq(self, bonus_eq: dict):
        """
        @param bonus_eq: assoc stat_code bonus_val
        """
        self.bonus_eq = bonus_eq
        self.effectiv_stats = self.base_stats.copy()

        for code_st, val in bonus_eq.items():
            if code_st not in self.effectiv_stats:
                self.effectiv_stats[code_st] = bonus_eq[code_st]
            elif code_st == PrimaryStats.Sadism:
                self.effectiv_stats[PrimaryStats.Sadism] += bonus_eq[PrimaryStats.Sadism]
            else:
                self.effectiv_stats[code_st] += bonus_eq[code_st]

    def get_xp(self):
        return self.__curr_xp

    def hack_inject_level(self, n):
        quantite_requise = StatsFramework().LVL_TO_XPT[n]
        self._set_xp(quantite_requise)

    def stack_xp(self, amount: int):
        """
        :param amount: quantité entière d'xp, strictement supérieur
        :return: int si nouveau level/None sinon
        """
        assert amount > 0
        res = self._set_xp(self.__curr_xp + amount)
        return res

    def _set_xp(self, amount):
        prior_level = self.get_level()
        self.__curr_xp = amount
        post_level = StatsFramework().calc_level(self.__curr_xp)
        if prior_level != post_level:
            self.__impacte_stats(post_level, self.bonus_eq)
            self.__level = post_level
            return post_level

    def get_level(self):
        return self.__level

    def get_increm_focus(self):
        return self._det_stat_secondaire(SecondaryStats.PowerIncrem)

    def get_curr_focus(self):
        return self.__curr_focus

    def check_hp_filled(self):
        return self.__curr_hp == self._det_stat_secondaire(SecondaryStats.MaxHp)

    def get_hp(self):
        # TODO généraliser usage, évite au joueur de se blesser en changeant equip.
        if self.__curr_hp == FULL_LIFE_SYM:
            return self.get_value(SecondaryStats.MaxHp)
        return self.__curr_hp

    def stack_hp(self, val):
        before = self.get_hp()
        after = before + val
        self.set_hp(after)
        self._cap_hp()

    def set_hp(self, val):
        assert isinstance(val, int)
        self.__curr_hp = val

    def shred_hp(self, ratio):
        """
        shred = diminue les pv suivant un ratio des pv max
        """
        cap = self.get_value(SecondaryStats.MaxHp, True)
        dmg = int(ratio * cap)
        self.set_hp(self.get_hp() - dmg)

    def is_alive(self):
        return self.get_hp() > 0

    def _cap_hp(self):
        bsup = self.get_value(SecondaryStats.MaxHp, True)
        if self.__curr_hp > bsup:
            self.__curr_hp = bsup

    def add_focus(self, val: int):
        self.__curr_focus += val
        max_foca = MAX_FOCUS
        if self.__curr_focus > max_foca:
            self.__curr_focus = max_foca

    def has_full_focus(self):
        max_foca = MAX_FOCUS
        return self.__curr_focus == max_foca

    def nullify_focus(self):
        self.__curr_focus = 0

    def set_max_focus(self, val):
        self.__max_focus = val
        res = False
        if self.__curr_focus >= self.__max_focus:
            self.__curr_focus %= self.__max_focus
            res = True
        return res

    def reset_focus_state(self):
        max_foca = MAX_FOCUS
        self.set_max_focus(max_foca)
        self.nullify_focus()

    def _det_stat_secondaire(self, stat_code):
        """
        :param stat_code:
        - paliers pour PowerIncrem
        willpower=1 y=1
        willpower=8 y=2
        willpower=19 y=3
        willpower=36 y=4
        willpower=65 y=5
        willpower=113 y=6
        willpower=192 y=7
        willpower=323 y=8
        :return:
        """
        if stat_code == SecondaryStats.MaxHp:
            en = self.get_value(PrimaryStats.Endurance, True)
            y = 92
            y += self.hp_per_en * en
            return y

        if stat_code == SecondaryStats.BaseDmg:
            fo = self.get_value(PrimaryStats.Strength, True)
            y = self.alpha + floor((self.beta * fo - 1) / (fo + self.gamma))
            return y

        if stat_code == SecondaryStats.ArmorClass:
            pe = self.get_value(PrimaryStats.Perception, True)
            y = floor(math.log(400 * (pe ** 4), 2)) - 8
            if y > self.armor_class_cap:
                y = self.armor_class_cap
            return y

        if stat_code == SecondaryStats.LifeSteal:
            sa = self.get_value(PrimaryStats.Sadism, True)
            y = math.log(1 + (sa / 196), 2) - 0.01
            if y < 0:
                y = 0.0
            elif y > self.lifesteal_cap:
                y = self.lifesteal_cap
            else:
                y = round(y, 2)
            return y

        if stat_code == SecondaryStats.PowerIncrem:
            x = self.get_value(PrimaryStats.Willpower, True)
            g = 2 * math.log((x + 9) * 0.1)  # retourne des valeurs dans l'intervalle 0-7
            if g > 7:
                g = 7
            y = 1 + floor(g)
            return y

        msg = 'invalid stat_code= {} for _det_stat_secondaire'.format(stat_code)
        raise ValueError(msg)

    def get_value(self, stat_code: int, with_buff=True):
        if stat_code in SecondaryStats.all_codes:
            return self._det_stat_secondaire(stat_code)
        if stat_code not in PrimaryStats.all_codes:
            msg = 'invalid stat_code= {} for _det_stat_primaire'.format(stat_code)
            raise ValueError(msg)
        if with_buff:
            res = self.effectiv_stats[stat_code]
        else:
            res = self.base_stats[stat_code]
        return res

    def __str__(self):
        res = '\n'
        for pstat_c in PrimaryStats.all_codes:
            res += ' {} : {}\n'.format(PrimaryStats.inv_map[pstat_c], self.get_value(pstat_c))
        res += '- - \n'
        for sec_stat_c in SecondaryStats.all_codes:
            res += ' {} : {}\n'.format(SecondaryStats.inv_map[sec_stat_c], self.get_value(sec_stat_c))
        return res


class Avatar(CogObject):
    def __init__(self, name, given_xp, gold):
        super().__init__()
        self._name = name
        self._owned = BelongingsModel(gold)
        self._stats = StatsKern(FULL_LIFE_SYM, given_xp, {})

    def add_gold(self, val):
        self._owned.gp += val
        self.pev(MyEvTypes.AvatarUpdate)

    def add_xp(self, val):
        self._stats.stack_xp(val)
        self.pev(MyEvTypes.AvatarUpdate)

    def get_team_desc(self):
        # returns str
        return self._owned.describe_lackeys()

    @property
    def level(self):
        return self._stats.get_level()

    @property
    def curr_xp(self):
        return self._stats.get_xp()

    @property
    def xp_next_level(self):
        _f = StatsFramework()
        curr_level = self._stats.get_level()
        if curr_level >= _f.get_max_level():
            return None
        return _f.LVL_TO_XPT[curr_level+1]

    @property
    def portrait_code(self):  # retro-compatibility
        return 0

    @property
    def tokenwealth(self):  # premium money
        return 0

    @property
    def gold(self):  # base money
        return self._owned.gp

    @property
    def name(self):
        return self._name

    def __str__(self):
        res = ''
        res += self._name + ' | '
        res += str(self._owned.gp) + '$ | stats{ '
        res += str(self._stats) + '}'
        return res


class Artifact:
    def __init__(self, acode, element):
        if acode not in ArtifactCodes.all_codes:
            raise ValueError('non-valid artifact code ({})'.format(acode))
        if (not isinstance(element, int)) or (element not in ArtifactNames[acode]):
            raise ValueError('non-valid artifact element ({}, code={})'.format(element, acode))
        self._code = acode
        self._elt = element

    @classmethod
    def gen_random(cls):
        c = random.choice(ArtifactCodes.all_codes)
        omega_elt = list(ArtifactNames[c].keys())
        omega_elt.remove(0)
        return cls(c, random.choice(omega_elt))

    def __str__(self):
        res = '[{}]\n'.format(ArtifactNames[self._code][0])
        res += '{}'.format(ArtifactNames[self._code][self._elt])
        return res


class BelongingsModel:
    """
    Modelise tt ce que l'avatar peut collectionner/posséder.
    Dans le game design on a imaginé 7 ressources:

    - Xp

    - gold pieces
    - items héros
    - artifacts (collectibles)
    - mana points, potion of mana
    - lackeys (up to 5)
    - enchantments (-> progrès temporaire/permanent)

    A part l'Xp tout est modélisé via cette classe
    """

    def __init__(self, gp, lackey_list=None):
        self.gp = gp
        self._eq_items = {
            'head': None, 'hands': None, 'torso': None, 'legs': None
        }
        self._artifacts = create_artifact_storage()
        self._mp = MAX_MANA_PTS
        if lackey_list:
            self.lackeys = lackey_list
        else:
            self.lackeys = [None for _ in range(BASE_LIMIT_LACKEYS)]
            self._init_random_lackeys()
        self._enchantments = set()

    def _init_random_lackeys(self):
        self.lackeys[0] = LackeyCodes.SmallOrc
        if random.random() < 0.6:
            self.lackeys[1] = LackeyCodes.FriendlySpider
            if random.random() < 0.6:
                self.lackeys[2] = LackeyCodes.Slime
                if random.random() < 0.5:
                    self.lackeys[3] = LackeyCodes.MountainTroll

    def describe_lackeys(self):
        res = ''
        cpt = 0
        for t in self.lackeys:
            if t:
                cpt += 1
        res += '{} lackeys'.format(cpt)
        if cpt:
            res += ':\n'
        for ii in range(cpt):
            # lackey code, to str
            res += ' - {}'.format(LackeyCodes.inv_map[self.lackeys[ii]])
            if ii != cpt-1:
                res += '\n'
        return res


"""
testing the stats framework + the Avatar class
"""
if __name__ == '__main__':
    sf = StatsFramework()
    print('max level?')
    print(sf.get_max_level())
    print()

    print('xp threshold Lvl 2-10?')
    for i in range(2, 11):
        print(sf.LVL_TO_XPT[i])
    print()

    xp = random.randint(8734, 65531*5)
    print('what lvl if i have {} xp?'.format(xp))
    print(sf.calc_level(xp))
    print()
    av = Avatar('roger', 125, 35666)
    print('avatar model e.g.')
    print(av)