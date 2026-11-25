import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}

/** Natives <dialog>: Fokusfalle und Escape gibt es gratis. Auf dem Handy als Vollbild. */
export function Dialog({ open, title, onClose, children, wide = false }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? "dialog--wide" : ""}`}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-label={title}
    >
      <div className="dialog__inner">
        <header className="dialog__head">
          <h2>{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Schließen">
            ✕
          </button>
        </header>
        {open && children}
      </div>
    </dialog>
  );
}
