# -*- coding: utf-8 -*-
"""Texto único (fuente compartida) del Aviso de Privacidad y Autorización
para el Tratamiento de Datos Personales.

Streamlit lo importa directamente; el backend FastAPI lo expone via
`GET /api/consentimiento/politica` para que el frontend React lo muestre.
Mantener este texto en un solo lugar evita que las dos interfaces
(React y Streamlit) queden desincronizadas.

`VERSION_POLITICA` debe incrementarse cada vez que cambie el texto de
fondo (NO cuando solo cambia el nombre del programa -- eso es
cosmético, no un cambio del marco legal). El gate de consentimiento
(backend y ambos frontends) es version-aware: si un usuario ya aceptó
una version anterior, se le vuelve a pedir aceptar la version vigente.

El nombre del programa académico es un PARÁMETRO (texto_politica()),
no una constante -- cada uno de los ~15 programas ve su propio nombre
en el mismo texto legal institucional, sin que eso cuente como una
nueva versión."""

VERSION_POLITICA = "1.1"

TITULO_POLITICA = "Aviso de Privacidad y Autorización para el Tratamiento de Datos Personales"


def acepto_politica_vigente(usuario) -> bool:
    """True si `usuario` (con atributos acepto_tratamiento_datos y
    version_politica_aceptada) ya acepto la VERSION_POLITICA vigente.
    Si el texto cambia de version, un usuario que acepto una version
    anterior debe volver a aceptar."""
    return bool(usuario.acepto_tratamiento_datos) and usuario.version_politica_aceptada == VERSION_POLITICA

_TEXTO_POLITICA_PLANTILLA = """\
**Sistema de Gestión y Autoevaluación Docente — Prueba piloto**
**Programa de {programa}, Universidad del Pacífico**

**1. Naturaleza piloto de la aplicación.** Este sistema se encuentra en fase de \
**prueba piloto** dentro del Programa de {programa} de la Universidad \
del Pacífico. Su uso está restringido al personal autorizado del programa \
(docentes, Director, Secretario Académico y Secretaria del Programa) y su \
finalidad es exclusivamente académico-administrativa e interna. Al tratarse de \
un piloto, la información registrada puede ajustarse, depurarse o reiniciarse \
mientras se evalúa el funcionamiento de la herramienta, previo al análisis de \
su eventual puesta en producción.

**2. Responsable del tratamiento.** La **Universidad del Pacífico**, institución \
de educación superior de carácter público con domicilio en Buenaventura, Valle \
del Cauca, Colombia, a través de su Programa de {programa}, actúa \
como responsable del tratamiento de los datos personales recolectados por este \
sistema.

**3. Autoría y desarrollo del sistema.** El diseño, desarrollo e implementación \
técnica de esta aplicación estuvieron a cargo del ingeniero **Wilman Andrés \
Quiñonez Valencia**, Ingeniero de Sistemas, quien actúa como encargado del \
tratamiento para efectos del desarrollo, soporte técnico y mantenimiento de la \
plataforma durante la fase piloto, bajo la dirección y responsabilidad del \
Programa de {programa} de la Universidad del Pacífico.

**4. Infraestructura y alojamiento.** Durante la fase piloto, esta aplicación se \
aloja en un servidor privado (VPS — *Virtual Private Server*) y se publica bajo \
un **dominio privado**, de acceso restringido y sin indexación ni difusión \
pública, con el fin de limitar la exposición de la información exclusivamente \
al personal autorizado del Programa mencionado en este aviso.

**5. Marco jurídico aplicable.** Este tratamiento de datos personales se rige, \
entre otras, por las siguientes normas vigentes en Colombia:

- Constitución Política de Colombia de 1991, artículo 15 (derecho fundamental a \
la intimidad y al Habeas Data).
- Ley Estatutaria 1581 de 2012, "Por la cual se dictan disposiciones generales \
para la protección de datos personales".
- Decreto Reglamentario 1377 de 2013, hoy compilado en el Decreto Único \
Reglamentario 1074 de 2015 (Título 2, Capítulo 25, Sector Comercio, Industria y \
Turismo).
- Sentencia C-748 de 2011 de la Corte Constitucional, que revisó la \
constitucionalidad de la Ley 1581 de 2012.
- **Ley 1273 de 2009**, "Por medio de la cual se modifica el Código Penal, se \
crea un nuevo bien jurídico tutelado — denominado *"de la protección de la \
información y de los datos"*— y se preservan integralmente los sistemas que \
utilicen las tecnologías de la información y las comunicaciones", que tipifica \
como delito el acceso abusivo a sistemas informáticos, la interceptación de \
datos y la violación de datos personales (artículo 269F del Código Penal), \
entre otras conductas.
- Ley 1712 de 2014, "Ley de Transparencia y del Derecho de Acceso a la \
Información Pública Nacional", aplicable a la Universidad del Pacífico como \
sujeto obligado de naturaleza pública, sin perjuicio de la reserva legal que \
protege los datos personales conforme al artículo 18 de dicha ley.
- Ley 594 de 2000, Ley General de Archivos, en lo relativo a la gestión \
documental y archivística de la información institucional.
- Circular Externa No. 002 de 2015 de la Superintendencia de Industria y \
Comercio (SIC) — Delegatura para la Protección de Datos Personales, sobre el \
deber de informar al Titular.
- Las demás normas que las adicionen, modifiquen, reglamenten o sustituyan.

La **Superintendencia de Industria y Comercio (SIC)** es la autoridad nacional \
de protección de datos personales, ante quien el Titular puede presentar \
consultas, quejas o reclamos relacionados con el tratamiento de su información.

**6. Finalidades del tratamiento.** Los datos personales y documentos \
registrados en este sistema se usan única y exclusivamente para: gestión \
académica y administrativa del Programa; autoevaluación y seguimiento de la \
gestión docente por periodo, semestre y corte; generación de informes y \
reportes en PDF; administración del calendario académico institucional; \
recepción, revisión, aprobación y custodia de soportes documentales (listas de \
asistencia, notas firmadas, informes de gestión docente, sílabos y programas de \
asignatura); administración de cuentas de usuario y roles de acceso; y envío de \
notificaciones internas asociadas a estos procesos.

**7. Datos objeto de tratamiento.** Datos de identificación y contacto (nombre \
completo, cédula, correo electrónico, teléfono, usuario de acceso); datos \
académicos y de desempeño docente (asignaturas a cargo, informes de gestión, \
indicadores agregados por corte); y los documentos que cada docente cargue en \
cumplimiento de sus funciones. Las calificaciones de estudiantes que puedan \
figurar dentro de los soportes cargados se tratan bajo la misma \
confidencialidad y reserva académica, y no se comparten con terceros ajenos al \
Programa.

**8. Derechos del Titular (Habeas Data).** Conforme al artículo 8 de la Ley \
1581 de 2012, el Titular de los datos tiene derecho a: conocer, actualizar y \
rectificar sus datos personales; solicitar prueba de la autorización otorgada; \
ser informado sobre el uso dado a sus datos; presentar quejas ante la SIC; \
revocar la autorización y/o solicitar la supresión del dato cuando no exista un \
deber legal o contractual de conservarlo; y acceder de forma gratuita a sus \
datos personales.

**9. Canal para ejercer estos derechos.** Estos derechos pueden ejercerse en \
cualquier momento ante la Dirección o la Secretaría Académica del Programa de \
{programa} de la Universidad del Pacífico.

**10. Medidas de seguridad.** El sistema aplica control de acceso basado en \
roles (RBAC) validado tanto en la interfaz como en cada servicio del backend; \
almacenamiento de contraseñas mediante cifrado unidireccional (hash); control \
de sesión mediante tokens (JWT); registro de trazabilidad de quién cargó, \
actualizó o aprobó cada documento; y alojamiento en un servidor y dominio \
privados (numeral 4), como medidas técnicas, administrativas y de \
infraestructura razonables para proteger la información durante la fase \
piloto, en línea con los deberes de seguridad de la Ley 1581 de 2012 y la \
protección penal de la Ley 1273 de 2009.

**11. Registro y prueba de la aceptación.** Cada vez que un Titular acepta este \
aviso, el sistema **guarda dicha aceptación de forma permanente en la base de \
datos** (usuario, fecha, hora y versión de la política aceptada), incluidas \
las aceptaciones de versiones anteriores de este documento, como prueba de la \
autorización otorgada conforme al artículo 9 de la Ley 1581 de 2012. Si el \
contenido de esta política cambia de forma sustancial, se le solicitará al \
Titular aceptar nuevamente la versión vigente antes de continuar usando el \
sistema.

**12. Vigencia.** Esta autorización rige mientras se desarrolle la prueba \
piloto y subsistan las finalidades aquí descritas. Si el sistema pasa a \
producción de manera definitiva, se informará oportunamente cualquier cambio a \
esta política.

**13. Declaración de aceptación.** Al marcar la casilla de aceptación y \
continuar, usted declara que ha leído y comprendido este aviso, y que otorga de \
manera **libre, previa, expresa e informada** su autorización a la Universidad \
del Pacífico — Programa de {programa} para el tratamiento de sus \
datos personales conforme a lo aquí descrito, en los términos de los artículos \
9 y 10 de la Ley 1581 de 2012. Esta aceptación es obligatoria para acceder al \
sistema, independientemente del rol asignado (Docente, Director, Secretario \
Académico o Secretaria del Programa)."""


def texto_politica(programa_nombre: str) -> str:
    """Arma el texto del aviso de privacidad con el nombre del programa
    académico del usuario que lo está aceptando. Ver docstring del
    módulo -- el nombre del programa es lo único que varía; el marco
    legal y `VERSION_POLITICA` son los mismos para todos los
    programas."""
    return _TEXTO_POLITICA_PLANTILLA.format(programa=programa_nombre)
