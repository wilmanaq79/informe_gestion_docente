export default function Spinner({ texto }: { texto?: string }) {
  return (
    <div className="cargando-linea">
      <span className="spinner" aria-hidden="true" />
      <span>{texto ?? "Cargando…"}</span>
    </div>
  );
}
