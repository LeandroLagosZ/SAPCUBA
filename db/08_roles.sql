-- Acceso al sistema con los roles del motor PostgreSQL (no hay tabla de usuarios ni de contraseñas).
-- La pantalla de acceso se conecta a PostgreSQL con el usuario y la contraseña que escribe la persona; PostgreSQL
-- valida la contraseña. El rol en SAPCUBA depende del grupo al que pertenece el usuario:
--   sapcuba_admin  -> ADMIN : todo (bajas, activaciones, agencias, respaldos)
--   sapcuba_agente -> AGENTE: aperturas, consultas, edición y reportes
-- Este script va al final: los permisos se otorgan sobre las tablas, vistas y funciones ya creadas (01 a 07).
-- Requiere un usuario con permiso CREATEROLE (por ejemplo postgres).
--
-- Usuarios de prueba (cámbialos con ALTER ROLE ... PASSWORD): admin / Admin123 y agente / Agente123.
-- Para crear otro usuario:  CREATE ROLE maria LOGIN PASSWORD '...' IN ROLE sapcuba_agente;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sapcuba_admin') THEN
    CREATE ROLE sapcuba_admin NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sapcuba_agente') THEN
    CREATE ROLE sapcuba_agente NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin') THEN
    CREATE ROLE "admin" LOGIN PASSWORD 'Admin123' IN ROLE sapcuba_admin;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente') THEN
    CREATE ROLE "agente" LOGIN PASSWORD 'Agente123' IN ROLE sapcuba_agente;
  END IF;
END $$;

COMMENT ON ROLE sapcuba_admin  IS 'SAPCUBA: administrador';
COMMENT ON ROLE sapcuba_agente IS 'SAPCUBA: agente de agencia';
COMMENT ON ROLE "admin"        IS 'Administrador del sistema';
COMMENT ON ROLE "agente"       IS 'Agente de agencia';

-- Nadie ejecuta funciones o procedimientos si no se le otorga expresamente
REVOKE ALL ON ALL ROUTINES IN SCHEMA public FROM PUBLIC;
-- Las dos funciones que necesita cualquier usuario al conectarse
GRANT EXECUTE ON FUNCTION fn_sesion_actual(), fn_salud() TO PUBLIC;

GRANT USAGE ON SCHEMA public TO sapcuba_admin, sapcuba_agente;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sapcuba_admin, sapcuba_agente;

-- Administrador: lee y escribe todo (nunca DELETE: las bajas son lógicas) y ejecuta todos los procedimientos
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO sapcuba_admin;
GRANT EXECUTE ON ALL ROUTINES IN SCHEMA public TO sapcuba_admin;

-- Agente: lee todo y solo escribe en las tablas de la apertura de cuentas (no toca agencias ni catálogos)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sapcuba_agente;
GRANT INSERT, UPDATE ON cliente, telefono_clientes, cuenta_ahorros, tarjeta TO sapcuba_agente;

-- Agente: puede ejecutar todo salvo las bajas, las activaciones y la gestión de agencias
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT p.oid::regprocedure AS firma
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.prokind IN ('f', 'p')
      AND p.proname NOT IN ('sp_cliente_eliminar', 'sp_cliente_activar',
                            'sp_agencia_crear', 'sp_agencia_editar', 'sp_agencia_eliminar',
                            'sp_agencia_activar', 'sp_agencia_cambiar_estado',
                            'sp_cuenta_eliminar', 'sp_cuenta_activar', 'sp_tarjeta_eliminar')
  LOOP
    EXECUTE format('GRANT EXECUTE ON ROUTINE %s TO sapcuba_agente', r.firma);
  END LOOP;
END $$;
