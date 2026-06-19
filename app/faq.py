from difflib import SequenceMatcher

FAQS = [
    {
        "pregunta": "¿Cuáles son los horarios de atención?",
        "respuesta": "Nuestro horario de atención es de lunes a viernes de 8:00 AM a 6:00 PM, y sábados de 9:00 AM a 1:00 PM.",
        "categoria": "general"
    },
    {
        "pregunta": "¿Qué métodos de pago aceptan?",
        "respuesta": "Aceptamos transferencias bancarias, tarjetas de crédito/débito (Visa, Mastercard, American Express), Nequi, Daviplata y efectivo contraentrega.",
        "categoria": "pagos"
    },
    {
        "pregunta": "¿Cuánto tiempo tarda la entrega?",
        "respuesta": "Los tiempos de entrega varían según tu ubicación: Bogotá 1-2 días hábiles, principales ciudades 2-4 días hábiles, y zonas rurales 5-7 días hábiles.",
        "categoria": "envios"
    },
    {
        "pregunta": "¿Cuál es la cobertura de envío?",
        "respuesta": "Realizamos envíos a todo el territorio colombiano, incluyendo ciudades principales, municipios y zonas rurales con cobertura de servicios de mensajería.",
        "categoria": "envios"
    },
    {
        "pregunta": "¿Cómo puedo hacer seguimiento a mi pedido?",
        "respuesta": "Puedes hacer seguimiento a tu pedido proporcionándonos tu número de pedido. También recibirás un enlace de seguimiento por WhatsApp cuando tu pedido sea despachado.",
        "categoria": "pedidos"
    },
    {
        "pregunta": "¿Tienen garantía sus productos?",
        "respuesta": "Sí, todos nuestros productos tienen una garantía de 6 meses por defectos de fábrica. La garantía cubre reparación o cambio del producto sin costo adicional.",
        "categoria": "garantias"
    },
    {
        "pregunta": "¿Cuál es la política de devolución?",
        "respuesta": "Aceptamos devoluciones dentro de los primeros 15 días calendario después de recibir el producto. El producto debe estar sin uso y en su empaque original. El costo del envío de devolución corre por cuenta del cliente.",
        "categoria": "devoluciones"
    },
    {
        "pregunta": "¿Cómo solicito una devolución?",
        "respuesta": "Para solicitar una devolución, contáctanos por WhatsApp indicando tu número de pedido y el motivo de la devolución. Te enviaremos las instrucciones para realizar el proceso.",
        "categoria": "devoluciones"
    },
    {
        "pregunta": "¿Hacen envíos internacionales?",
        "respuesta": "Actualmente solo realizamos envíos dentro de Colombia. No contamos con servicio de envíos internacionales por el momento.",
        "categoria": "envios"
    },
    {
        "pregunta": "¿Cuál es el costo del envío?",
        "respuesta": "El costo de envío depende de tu ubicación y el peso del pedido. En Bogotá el envío es gratuito para pedidos mayores a $100,000 COP. Para otras ciudades, el costo varía entre $8,000 y $25,000 COP.",
        "categoria": "envios"
    },
    {
        "pregunta": "¿Cómo puedo cancelar mi pedido?",
        "respuesta": "Puedes cancelar tu pedido si aún no ha sido despachado. Comunícate con nosotros por WhatsApp con tu número de pedido y lo cancelaremos sin costo alguno.",
        "categoria": "pedidos"
    },
    {
        "pregunta": "¿Cómo cambio mi dirección de envío?",
        "respuesta": "Si tu pedido aún no ha sido despachado, puedes cambiar la dirección de envío contactándonos por WhatsApp con tu número de pedido y la nueva dirección.",
        "categoria": "pedidos"
    },
    {
        "pregunta": "¿Aceptan pagos contraentrega?",
        "respuesta": "Sí, aceptamos pago contraentrega en Bogotá y principales ciudades. El pago se realiza en efectivo al momento de recibir el producto.",
        "categoria": "pagos"
    },
    {
        "pregunta": "¿Cuánto tarda la confirmación del pago?",
        "respuesta": "La confirmación del pago es inmediata para pagos con tarjeta, Nequi y Daviplata. Para transferencias bancarias puede tardar hasta 2 horas hábiles.",
        "categoria": "pagos"
    },
    {
        "pregunta": "¿Ofrecen factura electrónica?",
        "respuesta": "Sí, generamos factura electrónica para todos nuestros pedidos. La recibirás en tu correo electrónico una vez el pedido sea confirmado.",
        "categoria": "facturacion"
    },
    {
        "pregunta": "¿Qué hago si mi producto llega dañado?",
        "respuesta": "Si tu producto llega dañado, por favor contáctanos dentro de las primeras 24 horas enviando fotos del producto y el empaque. Gestionaremos el cambio sin costo adicional.",
        "categoria": "garantias"
    },
    {
        "pregunta": "¿Tienen tienda física?",
        "respuesta": "Actualmente operamos exclusivamente de manera online. No contamos con tienda física, pero puedes ver todos nuestros productos a través de nuestro catálogo de WhatsApp.",
        "categoria": "general"
    },
    {
        "pregunta": "¿Cómo puedo contactar a un asesor?",
        "respuesta": "Puedes contactar a un asesor directamente por este mismo canal solicitando hablar con un humano. Te conectaremos con uno de nuestros agentes de inmediato.",
        "categoria": "general"
    },
    {
        "pregunta": "¿Los precios incluyen IVA?",
        "respuesta": "Sí, todos nuestros precios incluyen el IVA. El precio que ves es el precio final que pagarás, sin cargos adicionales.",
        "categoria": "facturacion"
    },
    {
        "pregunta": "¿Cómo puedo saber el estado de mi pedido?",
        "respuesta": "Para conocer el estado de tu pedido, solo indícame tu número de pedido y consultaré la información actualizada en nuestro sistema.",
        "categoria": "pedidos"
    },
    {
        "pregunta": "¿Qué medios de contacto tienen?",
        "respuesta": "Puedes contactarnos por WhatsApp, correo electrónico y nuestro formulario de contacto en la página web. Nuestro equipo responde en un máximo de 2 horas hábiles.",
        "categoria": "general"
    },
    {
        "pregunta": "¿Hacen domicilios los fines de semana?",
        "respuesta": "Sí, realizamos domicilios los sábados de 9:00 AM a 1:00 PM. Los domingos y festivos no contamos con servicio de entrega.",
        "categoria": "envios"
    },
]


def cargar_faqs():
    return FAQS


def buscar_faq_similar(mensaje, umbral=0.3):
    mensaje = mensaje.lower().strip()
    mejores = []

    for faq in FAQS:
        pregunta = faq["pregunta"].lower()
        razon = SequenceMatcher(None, mensaje, pregunta).ratio()
        palabras_pregunta = set(pregunta.split())
        palabras_mensaje = set(mensaje.split())
        interseccion = len(palabras_pregunta & palabras_mensaje)
        union = len(palabras_pregunta | palabras_mensaje)
        jaccard = interseccion / union if union > 0 else 0

        puntaje = max(razon, jaccard * 0.8)
        if puntaje >= umbral:
            mejores.append((puntaje, faq))

    mejores.sort(key=lambda x: x[0], reverse=True)
    return [faq for _, faq in mejores[:3]] if mejores else []
