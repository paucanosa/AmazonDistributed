# -*- coding: utf-8 -*-
"""
File: OntoNamespaces

Created on 31/01/2014 8:55

Diversos namespaces utiles y algunas clases y propiedades de esos namespaces

@author: pau-laia-anna

"""
__author__ = 'pau-laia-anna'

from rdflib import Graph, RDF, RDFS, OWL, Namespace, Literal

# FIPA ACL Ontology
ACL = Namespace("http://www.nuin.org/ontology/fipa/acl#")

# OWL- S Ontology
OWLSService = Namespace('http://www.daml.org/services/owl-s/1.2/Service.owl#')
OWLSProfile = Namespace('http://www.daml.org/services/owl-s/1.2/Profile.owl#')

# Schema org ontology
SCHEMA = Namespace('http://schema.org/')

# Tickets Ontology
TIO = Namespace('http://purl.org/tio/ns#')

# Good relations
GR = Namespace('http://purl.org/goodrelations/v1#')

# DBPedia
DBP = Namespace('http://dbpedia.org/ontology/')

# Basic Geo (WGS84 lat/long) Vocabulary
GEO = Namespace('http://www.w3.org/2003/01/geo/wgs84_pos#')

# Directory Service Ontology
DSO = Namespace('http://www.semanticweb.org/directory-service-ontology#')

# ECSDI Ontology Namespace
ONTO = Namespace('http://www.owl-ontologies.com/OntologiaECSDI.owl#')

