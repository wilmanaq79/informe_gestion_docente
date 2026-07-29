export interface Usuario {
  id: number;
  nombre_completo: string;
  username: string;
  rol: "docente" | "director" | "secretario" | "secretaria_programa";
  activo: boolean;
  acepto_tratamiento_datos: boolean;
  debe_cambiar_password: boolean;
  programa_id: number | null;
  programa_nombre: string | null;
}

export interface Politica {
  version: string;
  titulo: string;
  texto: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  usuario: Usuario;
}

export interface EstudianteNota {
  nombre: string;
  documento: string | null;
  corte1: number | null;
  corte2: number | null;
  corte3: number | null;
  def_pond: number;
  nota_necesaria: number | null;
  estado: EstadoProgreso;
}

export type EstadoProgreso =
  | "asegurado"
  | "en_riesgo"
  | "matematicamente_reprobado"
  | "aprobado"
  | "reprobado";

export interface PdfPreview {
  materia_detectada: string | null;
  grupo: string | null;
  n_estudiantes: number;
  progreso: EstudianteNota[];
  conteo_estado: Record<string, number>;
}

export interface AsistenciaPreview {
  matriculados_asistencia: number;
  asistencia_regular: number;
}

export interface NotaSimple {
  nombre: string;
  nota: number;
}

export interface ResumenMateria {
  materia: string;
  grupo: string | null;
  matriculados: number;
  asistencia_regular: number | null;
  evaluados: number;
  aprobaron: number;
  es_estimado: boolean;
  promedio: number;
  mediana: number;
  desviacion: number;
  mejor_nombre: string;
  mejor_nota: number;
  coef_variacion: number;
  interpretacion: string;
  notas: NotaSimple[];
  conteo_estado: Record<string, number>;
}

export interface ProcesarResponse {
  resultados: ResumenMateria[];
  interpretacion_general: string;
  excel_base64: string;
  excel_filename: string;
}

export interface InformeCorte {
  id: number;
  corte_numero: number;
  corte_nombre: string;
  matriculados: number;
  asistencia_regular: number | null;
  evaluados: number;
  aprobaron: number;
  es_estimado: boolean;
  promedio: number | null;
  mediana: number | null;
  desviacion: number | null;
}

export interface Asignacion {
  id: number;
  asignatura: string;
  grupo: string | null;
  programa: string | null;
  informes: InformeCorte[];
}

export interface DocenteResumen {
  id: number;
  nombre_completo: string;
  materias_periodo: number;
  informes_cargados: number;
  ultimo_corte: number | null;
}

export interface DocenteDetalle {
  id: number;
  nombre_completo: string;
  cedula: string | null;
  email: string | null;
  asignaciones: Asignacion[];
}

export interface UsuarioCreate {
  nombre_completo: string;
  cedula: string;
  email: string;
  telefono?: string;
  username: string;
  password: string;
  rol: string;
}

export interface UsuarioUpdate {
  nombre_completo?: string;
  cedula?: string;
  email?: string;
  telefono?: string;
}

export interface UsuarioAdmin {
  id: number;
  nombre_completo: string;
  cedula: string | null;
  email: string | null;
  telefono: string | null;
  username: string;
  rol: string;
  activo: boolean;
}

export interface KpisInstitucionales {
  total_docentes: number;
  total_materias: number;
  total_matriculados: number;
  total_evaluados: number;
  total_aprobaron: number;
  promedio_general: number;
  pct_aprobacion_general: number;
}

export interface MateriaDashboard {
  materia: string;
  docente: string;
  grupo: string | null;
  corte_numero: number;
  corte_nombre: string;
  matriculados: number;
  evaluados: number;
  aprobaron: number;
  promedio: number;
  desviacion: number;
}

export interface CorteDashboard {
  corte_numero: number;
  matriculados: number;
  evaluados: number;
  aprobaron: number;
  promedio: number;
  pct_aprobacion: number;
}

export interface DocenteDashboard {
  docente: string;
  matriculados: number;
  evaluados: number;
  aprobaron: number;
  promedio: number;
  pct_aprobacion: number;
}

export interface Dashboard {
  kpis: KpisInstitucionales;
  por_materia: MateriaDashboard[];
  por_corte: CorteDashboard[];
  por_docente: DocenteDashboard[];
  conteo_estado_actual: Record<string, number>;
  generado_en: string;
}

export interface Periodo {
  id: number;
  nombre: string;
  anio: number;
  semestre: number;
  activo: boolean;
}

export interface EventoCalendario {
  id: number;
  periodo_id: number;
  actividad: string;
  fecha_inicio: string;
  fecha_fin: string | null;
  orden: number;
}

export interface FiltroAlcance {
  anio: number;
  semestre: number | null;
  corte: number | null;
}

export type EstadoEntrega = "pendiente" | "aprobado" | "rechazado";

export interface DocumentoEntrega {
  id: number;
  tipo_documento: string;
  descripcion_otro: string | null;
  materia: string | null;
  nombre_archivo: string;
  tamano_bytes: number;
  subido_en: string;
  firma_detectada: boolean | null;
  firma_confianza: string | null;
  firma_detalle: string | null;
  visto_en: string | null;
  revisado_manualmente: boolean;
  revisado_por_nombre: string | null;
  revisado_en: string | null;
}

export interface Entrega {
  id: number;
  docente_id: number;
  docente_nombre: string;
  periodo_id: number;
  periodo_nombre: string;
  corte_id: number;
  corte_numero: number;
  corte_nombre: string;
  estado: EstadoEntrega;
  documentos_firmados_confirmado: boolean;
  comentario_revision: string | null;
  revisado_por_nombre: string | null;
  revisado_en: string | null;
  notificacion_enviada: boolean;
  notificacion_error: string | null;
  creado_en: string;
  actualizado_en: string;
  todos_firmados_agente: boolean;
  documentos: DocumentoEntrega[];
}

export interface Notificacion {
  id: number;
  mensaje: string;
  entrega_id: number | null;
  leida: boolean;
  creado_en: string;
}

export interface RepositorioAsignatura {
  id: number;
  asignatura: string;
  docente_id: number | null;
  docente_nombre: string | null;
  silabo_nombre_archivo: string | null;
  silabo_tamano_bytes: number | null;
  programa_nombre_archivo: string | null;
  programa_tamano_bytes: number | null;
  creado_en: string;
  actualizado_en: string;
  creado_por_nombre: string | null;
  actualizado_por_nombre: string | null;
}
