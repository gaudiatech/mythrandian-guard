from app.BelongingsModel import Artifact
import random


class Loot:
    """
    After completing a mission,
    sometimes the player can choose between 2-3 rewards,
    sometimes he just gets extra gold.

    When you're choosing you can select:
    bonus xp
    bonus gold
    potion of mana (small, sometimes LARGE)
    or an artifact (when this occurs other bonuses are doubled)
    """

    def __init__(self, extra_xp, extra_gold, extra_mana, artifact):
        self._xp = extra_xp
        self._gold = extra_gold
        self._mana = extra_mana
        self._artifact = artifact

    @classmethod
    def gen_random(cls, mission_diff):
        """
        PROBA. TABLE

        0.033: artifact
        0.13: mana

        (things that stack)
        0.75: regular gold amount
        complement: regular xp amount
        """
        ptable = {
            0: 0.025,
            1: 0.10,
            2: 0.87
        }
        rem_loot_elt = 4
        # variables(4)
        # qui contiennent ensemble la future carte(comme une menu) des loot
        arti, mana, gold, xp = None, 0, 0, 0

        # limites de difficulte basees sur progression 2, 3, 5, 8, 13, 21
        nb_lancers = 4
        if mission_diff > 21:
            nb_lancers -= 3
        elif mission_diff > 13:
            nb_lancers -= 2
        elif mission_diff > 8:
            nb_lancers -= 1
        for _ in range(nb_lancers):
            if random.random() < ptable[0]:
                arti = Artifact.gen_random()
                rem_loot_elt -= 1
                break

        if mission_diff > 13 and random.random() < ptable[1]:
            mana += 1
            rem_loot_elt -= 1
        if mission_diff > 21 and random.random() < ptable[1]:
            mana += 1
            rem_loot_elt -= 1

        while rem_loot_elt > 0:
            if random.random() < ptable[2]:
                gold += random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)
            else:
                xp += int(3 * mission_diff**2)
            rem_loot_elt -= 1

        gold = int(gold * mission_diff)

        # special case: artifact => double other rewards, mana+2
        if arti is not None:
            if mana:
                mana += 2
            if gold:
                gold *= 2
            if xp:
                xp *= 2

        if mana and (gold > 0):
            gold += int(mana * mission_diff)
        if xp > 0:
            gold = int(gold*0.85)

        # None instead of 0
        mana = mana if mana else None
        gold = gold if gold else None
        xp = xp if xp else None
        return cls(xp, gold, mana, arti)

    def __str__(self):
        res = 'LOOT rewards:\n'
        if self._xp:
            res += 'xp: {}\n'.format(self._xp)
        if self._gold:
            res += 'gold: {}\n'.format(self._gold)
        if self._mana:
            res += 'mana: {}\n'.format(self._mana)
        if self._artifact:
            res += str(self._artifact) + '\n'
        return res
