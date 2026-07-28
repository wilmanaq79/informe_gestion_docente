interface Seccion {
  id: string;
  etiqueta: string;
}

/** Barra sticky de acceso rapido por anclas, para paginas largas con
 * varias tarjetas apiladas (evita scrollear a ciegas para llegar a una
 * seccion mas abajo, p.ej. Entrega de documentos o Repositorio). */
export default function SeccionNav({ secciones }: { secciones: Seccion[] }) {
  function irA(e: React.MouseEvent<HTMLAnchorElement>, id: string) {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <nav className="seccion-nav" aria-label="Navegación rápida por secciones">
      {secciones.map((s) => (
        <a key={s.id} href={`#${s.id}`} className="seccion-nav__link" onClick={(e) => irA(e, s.id)}>
          {s.etiqueta}
        </a>
      ))}
    </nav>
  );
}
