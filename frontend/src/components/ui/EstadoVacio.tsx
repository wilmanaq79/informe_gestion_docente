export default function EstadoVacio({ icono = "📭", texto }: { icono?: string; texto: string }) {
  return (
    <div className="estado-vacio">
      <span className="estado-vacio__icono" aria-hidden="true">
        {icono}
      </span>
      <span className="estado-vacio__texto">{texto}</span>
    </div>
  );
}
