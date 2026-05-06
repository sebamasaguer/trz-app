import enum


class RoutineType(str, enum.Enum):
    DIAS = "DIAS"
    SEMANAS = "SEMANAS"


class Role(str, enum.Enum):
    ADMINISTRADOR = "ADMINISTRADOR"
    ADMINISTRATIVO = "ADMINISTRATIVO"
    PROFESOR = "PROFESOR"
    ALUMNO = "ALUMNO"


class MembershipKind(str, enum.Enum):
    FUNCIONAL = "FUNCIONAL"
    MUSCULACION = "MUSCULACION"
    COMBINACION = "COMBINACION"
    CLASE_SUELTA = "CLASE_SUELTA"


class PaymentMethod(str, enum.Enum):
    LISTA = "LISTA"
    EFECTIVO = "EFECTIVO"
    TRANSFERENCIA = "TRANSFERENCIA"


class ServiceKind(str, enum.Enum):
    FUNCIONAL = "FUNCIONAL"
    MUSCULACION = "MUSCULACION"


class CashEntryType(str, enum.Enum):
    INGRESO = "INGRESO"
    EGRESO = "EGRESO"


class CashPaymentStatus(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    ACREDITADO = "ACREDITADO"
    ANULADO = "ANULADO"


class CashSessionStatus(str, enum.Enum):
    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"


class CashExpenseCategory(str, enum.Enum):
    MEMBRESIA = "MEMBRESIA"
    INSUMOS = "INSUMOS"
    LIMPIEZA = "LIMPIEZA"
    MANTENIMIENTO = "MANTENIMIENTO"
    SERVICIOS = "SERVICIOS"
    SUELDOS = "SUELDOS"
    VARIOS = "VARIOS"


class CommercialStage(str, enum.Enum):
    NUEVO = "NUEVO"
    INTERESADO = "INTERESADO"
    CALIFICADO = "CALIFICADO"
    NEGOCIANDO = "NEGOCIANDO"
    DERIVADO = "DERIVADO"
    REACTIVADO = "REACTIVADO"
    CERRADO = "CERRADO"
    PERDIDO = "PERDIDO"


class FollowupKind(str, enum.Enum):
    MOROSIDAD = "MOROSIDAD"
    INACTIVIDAD = "INACTIVIDAD"
    GENERAL = "GENERAL"


class FollowupStatus(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    CONTACTADO = "CONTACTADO"
    RESPONDIO = "RESPONDIO"
    REACTIVADO = "REACTIVADO"
    DESCARTADO = "DESCARTADO"


class FollowupPriority(str, enum.Enum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    CRITICA = "CRITICA"


class FollowupChannel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    LLAMADA = "LLAMADA"
    PRESENCIAL = "PRESENCIAL"
    OTRO = "OTRO"


class MessageTemplateChannel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    GENERAL = "GENERAL"


class FollowupActionType(str, enum.Enum):
    MENSAJE_ENVIADO = "MENSAJE_ENVIADO"
    LLAMADA = "LLAMADA"
    EMAIL_ENVIADO = "EMAIL_ENVIADO"
    WHATSAPP_ENVIADO = "WHATSAPP_ENVIADO"
    RECORDATORIO = "RECORDATORIO"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"
    NOTA = "NOTA"


class ProspectStatus(str, enum.Enum):
    NUEVO = "NUEVO"
    CALIFICANDO = "CALIFICANDO"
    INTERESADO = "INTERESADO"
    DERIVADO = "DERIVADO"
    CERRADO = "CERRADO"
    DESCARTADO = "DESCARTADO"


class ConversationType(str, enum.Enum):
    REACTIVACION = "REACTIVACION"
    NUEVO_PROSPECTO = "NUEVO_PROSPECTO"
    SOPORTE = "SOPORTE"
    GENERAL = "GENERAL"


class ConversationStatus(str, enum.Enum):
    ABIERTA = "ABIERTA"
    EN_AUTOMATICO = "EN_AUTOMATICO"
    DERIVADA_A_HUMANO = "DERIVADA_A_HUMANO"
    CERRADA = "CERRADA"


class SenderType(str, enum.Enum):
    BOT = "BOT"
    HUMANO = "HUMANO"
    ALUMNO = "ALUMNO"
    PROSPECTO = "PROSPECTO"
    SISTEMA = "SISTEMA"


class ClassStatus(str, enum.Enum):
    ACTIVA = "ACTIVA"
    INACTIVA = "INACTIVA"


class Weekday(str, enum.Enum):
    LUNES = "LUNES"
    MARTES = "MARTES"
    MIERCOLES = "MIERCOLES"
    JUEVES = "JUEVES"
    VIERNES = "VIERNES"
    SABADO = "SABADO"
    DOMINGO = "DOMINGO"


class EnrollmentStatus(str, enum.Enum):
    ACTIVA = "ACTIVA"
    CANCELADA = "CANCELADA"