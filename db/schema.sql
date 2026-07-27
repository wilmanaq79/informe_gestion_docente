-- =============================================================================
-- MARCO DE REFERENCIA DE LA BASE DE DATOS
-- Sistema de Gestion y Autoevaluacion Docente
-- Programa de Ingenieria de Sistemas -- Universidad del Pacifico
--
-- Generado automaticamente con `pg_dump --schema-only` a partir del esquema
-- real (creado por db/models.py con SQLAlchemy). Este archivo es solo
-- documentacion/referencia -- la fuente de verdad son los modelos en
-- db/models.py; para recrear la base de datos usa `python -m db.seed`.
--
-- Normalizacion:
--   roles, cortes, periodos_academicos      -> tablas de catalogo/referencia
--   usuarios                                -> docentes, director, secretario
--   asignaciones_academicas                 -> materia/grupo que dicta cada
--                                              docente en cada periodo
--   informes_corte                          -> Matriculados/Asistencia/
--                                              Evaluados/Aprobados por
--                                              asignacion y corte
--   notas_estudiantes                       -> detalle por estudiante que
--                                              respalda cada informe_corte
-- =============================================================================

--
-- PostgreSQL database dump
--

\restrict o4tB1oSaKepfjlC3iV0g7wGcGzZEqbH64ZkXvBt2mP4ihN5SxMjfloh9uaSE9g4

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: asignaciones_academicas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asignaciones_academicas (
    id integer NOT NULL,
    docente_id integer NOT NULL,
    periodo_id integer NOT NULL,
    asignatura character varying(150) NOT NULL,
    programa character varying(150),
    grupo character varying(30)
);


--
-- Name: asignaciones_academicas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.asignaciones_academicas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: asignaciones_academicas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.asignaciones_academicas_id_seq OWNED BY public.asignaciones_academicas.id;


--
-- Name: cortes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cortes (
    id integer NOT NULL,
    numero integer NOT NULL,
    nombre character varying(30) NOT NULL,
    peso_porcentual numeric(4,2) NOT NULL
);


--
-- Name: cortes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cortes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cortes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cortes_id_seq OWNED BY public.cortes.id;


--
-- Name: informes_corte; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.informes_corte (
    id integer NOT NULL,
    asignacion_id integer NOT NULL,
    corte_id integer NOT NULL,
    matriculados integer NOT NULL,
    asistencia_regular integer,
    evaluados integer NOT NULL,
    aprobaron integer NOT NULL,
    es_estimado boolean NOT NULL,
    promedio numeric(5,2),
    mediana numeric(5,2),
    desviacion numeric(5,2),
    generado_en timestamp without time zone NOT NULL
);


--
-- Name: informes_corte_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.informes_corte_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: informes_corte_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.informes_corte_id_seq OWNED BY public.informes_corte.id;


--
-- Name: notas_estudiantes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notas_estudiantes (
    id integer NOT NULL,
    informe_corte_id integer NOT NULL,
    documento character varying(30),
    nombre_estudiante character varying(150) NOT NULL,
    corte1 numeric(5,2),
    corte2 numeric(5,2),
    corte3 numeric(5,2),
    def_pond numeric(5,2) NOT NULL,
    nota_necesaria numeric(5,2),
    estado character varying(30) NOT NULL
);


--
-- Name: notas_estudiantes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notas_estudiantes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notas_estudiantes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notas_estudiantes_id_seq OWNED BY public.notas_estudiantes.id;


--
-- Name: periodos_academicos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.periodos_academicos (
    id integer NOT NULL,
    nombre character varying(20) NOT NULL
);


--
-- Name: periodos_academicos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.periodos_academicos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: periodos_academicos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.periodos_academicos_id_seq OWNED BY public.periodos_academicos.id;


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    nombre character varying(20) NOT NULL
);


--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    nombre_completo character varying(150) NOT NULL,
    cedula character varying(20),
    email character varying(120),
    telefono character varying(30),
    username character varying(50) NOT NULL,
    password_hash character varying(200) NOT NULL,
    rol_id integer NOT NULL,
    activo boolean NOT NULL,
    creado_en timestamp without time zone NOT NULL
);


--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: asignaciones_academicas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_academicas ALTER COLUMN id SET DEFAULT nextval('public.asignaciones_academicas_id_seq'::regclass);


--
-- Name: cortes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cortes ALTER COLUMN id SET DEFAULT nextval('public.cortes_id_seq'::regclass);


--
-- Name: informes_corte id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.informes_corte ALTER COLUMN id SET DEFAULT nextval('public.informes_corte_id_seq'::regclass);


--
-- Name: notas_estudiantes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notas_estudiantes ALTER COLUMN id SET DEFAULT nextval('public.notas_estudiantes_id_seq'::regclass);


--
-- Name: periodos_academicos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodos_academicos ALTER COLUMN id SET DEFAULT nextval('public.periodos_academicos_id_seq'::regclass);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Name: asignaciones_academicas asignaciones_academicas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_academicas
    ADD CONSTRAINT asignaciones_academicas_pkey PRIMARY KEY (id);


--
-- Name: cortes cortes_numero_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cortes
    ADD CONSTRAINT cortes_numero_key UNIQUE (numero);


--
-- Name: cortes cortes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cortes
    ADD CONSTRAINT cortes_pkey PRIMARY KEY (id);


--
-- Name: informes_corte informes_corte_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.informes_corte
    ADD CONSTRAINT informes_corte_pkey PRIMARY KEY (id);


--
-- Name: notas_estudiantes notas_estudiantes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notas_estudiantes
    ADD CONSTRAINT notas_estudiantes_pkey PRIMARY KEY (id);


--
-- Name: periodos_academicos periodos_academicos_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodos_academicos
    ADD CONSTRAINT periodos_academicos_nombre_key UNIQUE (nombre);


--
-- Name: periodos_academicos periodos_academicos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodos_academicos
    ADD CONSTRAINT periodos_academicos_pkey PRIMARY KEY (id);


--
-- Name: roles roles_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_nombre_key UNIQUE (nombre);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: asignaciones_academicas uq_asignacion; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_academicas
    ADD CONSTRAINT uq_asignacion UNIQUE (docente_id, periodo_id, asignatura, grupo);


--
-- Name: informes_corte uq_informe_por_corte; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.informes_corte
    ADD CONSTRAINT uq_informe_por_corte UNIQUE (asignacion_id, corte_id);


--
-- Name: usuarios usuarios_cedula_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_cedula_key UNIQUE (cedula);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_username_key UNIQUE (username);


--
-- Name: asignaciones_academicas asignaciones_academicas_docente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_academicas
    ADD CONSTRAINT asignaciones_academicas_docente_id_fkey FOREIGN KEY (docente_id) REFERENCES public.usuarios(id);


--
-- Name: asignaciones_academicas asignaciones_academicas_periodo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_academicas
    ADD CONSTRAINT asignaciones_academicas_periodo_id_fkey FOREIGN KEY (periodo_id) REFERENCES public.periodos_academicos(id);


--
-- Name: informes_corte informes_corte_asignacion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.informes_corte
    ADD CONSTRAINT informes_corte_asignacion_id_fkey FOREIGN KEY (asignacion_id) REFERENCES public.asignaciones_academicas(id);


--
-- Name: informes_corte informes_corte_corte_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.informes_corte
    ADD CONSTRAINT informes_corte_corte_id_fkey FOREIGN KEY (corte_id) REFERENCES public.cortes(id);


--
-- Name: notas_estudiantes notas_estudiantes_informe_corte_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notas_estudiantes
    ADD CONSTRAINT notas_estudiantes_informe_corte_id_fkey FOREIGN KEY (informe_corte_id) REFERENCES public.informes_corte(id) ON DELETE CASCADE;


--
-- Name: usuarios usuarios_rol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_rol_id_fkey FOREIGN KEY (rol_id) REFERENCES public.roles(id);


--
-- PostgreSQL database dump complete
--

\unrestrict o4tB1oSaKepfjlC3iV0g7wGcGzZEqbH64ZkXvBt2mP4ihN5SxMjfloh9uaSE9g4

