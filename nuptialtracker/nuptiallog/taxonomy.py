#
#  taxonomy.py
# AntNupTracker Server, backend for recording and managing ant nuptial flight data
# Copyright (C) 2020  Abouheif Lab
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# 

from .models import Genus, Species
import requests
import json
import os

def loadGenera(filename):
    file = open(filename, "r")
    genera = []

    for line in file:
        if (line.strip() == ""):
            continue

        if (line[0] == "#" or line[0:2]=="//"):
            continue

        #print(line)

        split = line.split(" ", 1)
        genus = split[0]

        #print(split)

        if (genus in genera):
            continue
        else:
            genera.append(genus)
    genera.append("Unknown")

    return genera

def loadSpecies(filename):
    file = open(filename, "r")
    species = {}

    for line in file:
        #print(line)

        if (line.strip() == ""):
            continue

        if (line[0] == "#" or line[0:2]=="//"):
            continue

        split = line.split(" ", 1)
        genus = split[0]
        spec = split[1].rstrip()

        #print(split)

        if (genus not in species.keys()):
            species[genus] = []

        (species[genus]).append(spec)

    species["Unknown"]=[]

    for genus in species.keys():
        species[genus].insert(0, "sp. (Unknown)")
    return species

def create_Genus_Objects(genera):
    for genus in genera:
        Genus.objects.create(name=genus)

def create_Species_Objects(taxonomy):
    for genus in taxonomy.keys():
        # print(genus)
        g = Genus.objects.get(name=genus)

        for species in taxonomy[genus]:
            Species.objects.create(genus=g, name=species)

SPECIES_FILE = os.getenv("TAXONOMY_FILE")
GENERA = loadGenera(SPECIES_FILE)
SPECIES = loadSpecies(SPECIES_FILE)

# UNKNOWN_GENUS = Genus.objects.get(name="Unknown")
# UNKNOWN_UNKNOWN = Species.objects.get(genus=UNKNOWN_GENUS, name="sp. (Unknown)")

def fetchTaxonomy(output):
    species = ["# Taxonomy from 'antwiki.org' - CC-BY-SA", "# List of species obtained from https://www.antwiki.org/wiki/index.php?title=Category:Extant_species"]
    initialUrl = "https://www.antwiki.org/wiki/api.php?action=query&list=categorymembers&cmtitle=Category:Extant_species&cmlimit=500&format=json"
    data = requests.get(initialUrl).json()

    species_frame = data["query"]["categorymembers"]

    species_names = [s["title"] for s in species_frame]

    species.extend(species_names)

    while True:
        try:
            cmcontinue = data["continue"]["cmcontinue"]
            new_url = initialUrl + f"&cmcontinue={cmcontinue}"
            data = requests.get(new_url).json()
            species_frame = data["query"]["categorymembers"]

            species_names = [s["title"] for s in species_frame]

            species.extend(species_names)

        except KeyError:
            break
        
    species = [s+"\n" for s in species]

    f = open(output, "w")
    f.writelines(species)
    f.close()