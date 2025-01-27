"""
Agente Centro Logístico.

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente


@author: pau-laia-anna
"""

import time, random
import argparse
import socket
import sys
import requests
from multiprocessing import Queue, Process
from flask import Flask, request
from pyparsing import Literal
from rdflib import URIRef, XSD, Namespace, Graph, Literal

#from Agentes import AgTransportista
from Util.ACLMessages import *
from Util.Agent import Agent
from Util.FlaskServer import shutdown_server
from Util.Logging import config_logger
from Util.OntoNamespaces import ONTO

__author__ = 'pau-laia-anna'
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()
port = 9014

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgCentroLogistico = Agent('AgCentroLogistico',
                          agn.AgCentroLogisticoBCN,
                          'http://%s:%d/comm' % (hostname, port),
                          'http://%s:%d/Stop' % (hostname, port))

AgGestorCompra = Agent('AgGestorCompra',
                       agn.AgGestorCompra,
                       'http://%s:9012/comm' % (hostname),
                       'http://%s:9012/Stop' % (hostname))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)

AgTransportista = Agent('AgTransportista',
                        agn.Transportista,
                        'http://%s:9015/comm' % hostname,
                        'http://%s:9015/Stop' % hostname)

AgVendedorExterno = Agent('AgVendedorExterno',
                        agn.AgVendedorExterno,
                        'http://%s:9018/comm' % hostname,
                        'http://%s:9018/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt


@app.route("/comm")
def communication():
    """
    Communication Entrypoint
    """
    global centro
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    gr = None
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgCentroLogistico.uri, msgcnt=get_count())
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgCentroLogistico.uri,
                               msgcnt=get_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de busqueda
            if accion == ONTO.ProcesarEnvio:
                #Se genera un grafo con la informacion necesaria para negociar el envío.
                count = get_count()
                action = ONTO["PedirPreciosEnvio_"+ str(count)]
                lote = ONTO["Lote_"+str(count)]
                graph = Graph()
                peso_total = 0
                graph.add((action, RDF.type, ONTO.PedirPreciosEnvio))
                graph.add((lote,RDF.type,ONTO.Lote))
                compraSujeto = ""
                ciudadCL = ""
                productos = []
                for s, p, o in gm:
                    if p == ONTO.Ciudad:
                        graph.add((lote, ONTO.Ciudad, Literal(o,datatype=XSD.string)))
                        compraSujeto = s
                    if p == ONTO.Identificador:
                        idLote = o
                    elif p == ONTO.PrioridadEntrega:
                        graph.add((lote, ONTO.PrioridadEntrega, Literal(o,datatype=XSD.float)))
                    elif p == ONTO.NombreCL:
                        graph.add((lote, ONTO.NombreCL,Literal(o,datatype=XSD.string)))
                        ciudadCL = o
                    elif p == ONTO.PrecioTotal:
                        precioCompra = o.toPython()
                    elif p == ONTO.Peso:
                        peso_total += float(o)
                    elif p == ONTO.Nombre:
                        productos.append(s)
                        graph.add((s, RDF.type, ONTO.Producto))
                        graph.add((s, ONTO.Nombre, Literal(o,datatype=XSD.string)))
                        graph.add((lote, ONTO.Contiene, s))
                graph.add((lote, ONTO.Peso, Literal(peso_total,datatype=XSD.float)))
                #La accion es pedir precios envio, y conteine un lote como informacion.
                graph.add((action, ONTO.Lote, lote))

                logger.info("Pedimos los precios de envío a los transportistas del centro logístico de " + ciudadCL)
                gr = send_message(
                    build_message(graph, ACL.request, AgCentroLogistico.uri, AgTransportista.uri, action, count), AgTransportista.address)

                logger.info("Hemos recibido las ofertas iniciales")

                gContraoferta = Graph()
                action = ONTO["PedirControfertasPreciosEnvio_"+ str(count)]
                gContraoferta.add((action, RDF.type, ONTO.PedirContraofertasPreciosEnvio))
                gContraoferta.add((lote, RDF.type, ONTO.Lote))
                gContraoferta.add((action, ONTO.LoteContraofertas, lote))


                transportista = []
                for s, p, o in gr:
                    if p == ONTO.OfertaDe:
                        transportista.append(o)
                precio_min = sys.maxsize
                for t in transportista:
                    precio = gr.value(subject=t, predicate=ONTO.PrecioTransporte)
                    if precio_min > precio.toPython():
                        precio_min = precio.toPython()
                contraoferta = precio_min * random.uniform(0.85, 0.95)
                gContraoferta.add((action, ONTO.PrecioTransporte, Literal(contraoferta)))

                logger.info("Pedimos que rebajen los precios ofreciéndoles una contraoferta de " + str(contraoferta) + " €")

                gFinal = send_message(
                    build_message(gContraoferta, ACL.request, AgCentroLogistico.uri, AgTransportista.uri, action, count), AgTransportista.address)

                logger.info("Hemos recibido las contraofertas de los transportistas")

                precioFinal = sys.maxsize
                transportistas = []
                for s, p, o in gFinal:
                    if p == ONTO.OfertaDe:
                        transportistas.append(o)
                idTransportistaFinal = "hola"
                transportistaFinal = "nom"
                fechaFinal = "data"
                if transportistas is not None:
                    logger.info("Algun transportista ha ofrecido una contraoferta")
                    logger.info("Elejimos el transportista que ha ofrecido una contraoferta más barata")
                    for t in transportistas:
                        precio = gFinal.value(subject=t, predicate=ONTO.PrecioTransporte)
                        if precio.toPython() < precioFinal:
                            precioFinal = precio.toPython()
                            transportistaFinal = gFinal.value(subject=t, predicate=ONTO.Nombre)
                            idTransportistaFinal = gFinal.value(subject=t, predicate=ONTO.Identificador)
                            fechaFinal = gFinal.value(subject=t, predicate=ONTO.Fecha)
                else:
                    logger.info("Todos los transportistas han rechazado la contraoferta")
                    for t in gr.objects(content, ONTO.Transportista):
                        precio = gr.value(subject=t, predicate=ONTO.PrecioTransporte)
                        if precio.toPython() < precioFinal:
                            precioFinal = precio.toPython()
                            transportistaFinal = gFinal.value(subject=t, predicate=ONTO.Nombre)
                            idTransportistaFinal = gFinal.value(subject=t, predicate=ONTO.Identificador)
                            fechaFinal = gFinal.value(subject=t, predicate=ONTO.Fecha)
                precioEnvio = precioFinal
                precioFinal += precioCompra

                transportista = ONTO[idTransportistaFinal]
                gm.add((transportista,RDF.type,ONTO.Transportista))
                gm.add((transportista,ONTO.NombreTransportista,Literal(transportistaFinal)))
                gm.add((compraSujeto, ONTO.EntregadaPor, transportista))
                gm.add((compraSujeto, ONTO.Lote, lote))
                gm.add((compraSujeto, ONTO.FechaEntrega, Literal(fechaFinal)))
                gm.add((compraSujeto, ONTO.PrecioTotalCompra, Literal(precioFinal)))
                grafo_confirmacion = Graph()
                accion = ONTO["EnviarPaquete_" + str(count)]
                grafo_confirmacion.add((accion, RDF.type, ONTO.EnviarPaquete))
                grafo_confirmacion.add((accion, ONTO.Identificador, Literal(idTransportistaFinal)))
                grafo_confirmacion.add((transportista, ONTO.NombreTransportista, Literal(transportistaFinal)))
                grafo_confirmacion.add((accion, ONTO.LoteFinal, idLote))

                logger.info("El transportista elejido es " + transportistaFinal + ", que entregará el lote por " + str(precioEnvio))

                hay_prod_ext = False
                for p in productos:
                    if p[:58] != "http://www.owl-ontologies.com/OntologiaECSDI.owl#Producto_":
                        hay_prod_ext = True

                if hay_prod_ext:
                    empezar_proceso = Process(target=avisar_vendedores_externos, args=())
                    empezar_proceso.start()
                p = Process(target=confirmacion,args=(grafo_confirmacion,accion))
                p.start()
                return gm.serialize(format="xml"), 200

            elif accion == ONTO.CobrarCompra:
                for s,p,o in gm:
                    if p == ONTO.LoteEntregado:
                        idLote = str(o)
                        break
                g = Graph()
                action = ONTO["CobrarCompra_" + str(get_count())]
                g.add((action, RDF.type, ONTO.CobrarCompra))
                g.add((action, ONTO.LoteEntregado, Literal(idLote)))
                p = Process(target=confirmacion_entregado_gestor,args=(g,action))
                p.start()
                grr = Graph()
                return grr.serialize(format="xml"),200
            else:
                resposta= Graph()
                return resposta.serialize(format="xml"),200


def avisar_vendedores_externos():
    g = Graph()
    action = ONTO["AvisarEnvio_" + str(get_count())]
    g.add((action, RDF.type, ONTO.AvisarEnvio))
    send_message(
        build_message(g, ACL.request, AgCentroLogistico.uri, AgVendedorExterno.uri, action, get_count()), AgVendedorExterno.address)


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def confirmacion_entregado_gestor(g=Graph(),action=""):
    send_message(
        build_message(g, ACL.request, AgCentroLogistico.uri, AgGestorCompra.uri, action, get_count()), AgGestorCompra.address)


def confirmacion(g=Graph(),action=""):
    send_message(
        build_message(g, ACL.request, AgCentroLogistico.uri, AgTransportista.uri, action, get_count()), AgTransportista.address)


def agentbehavior1(cola):
    """
    Un comportamiento del agente

    :return:
    """
    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()

    print('The End')