package com.autentication.config;

import com.zaxxer.hikari.HikariDataSource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.core.env.Environment;
import org.springframework.core.type.AnnotatedTypeMetadata;

import javax.sql.DataSource;
import java.net.URI;

/**
 * Construye el {@link DataSource} a partir de una única variable de entorno
 * {@code DATABASE_URL} (formato PostgreSQL, como la que entrega Supabase):
 *
 * <pre>postgresql://usuario:password@host:puerto/basededatos</pre>
 *
 * <p>Solo se activa si {@code DATABASE_URL} está definida y NO vacía. Si no,
 * Spring Boot usa la configuración estándar de {@code spring.datasource.*}
 * (H2 en local).</p>
 *
 * <p>Si se define {@code DB_SCHEMA}, se añade automáticamente como
 * {@code currentSchema=<schema>} para usar un esquema dedicado dentro de la
 * misma base de datos (p. ej. {@code auth}).</p>
 */
@Configuration
@Conditional(DatabaseConfig.DatabaseUrlPresent.class)
@Slf4j
public class DatabaseConfig {

    /** Condición: DATABASE_URL presente y con valor no vacío. */
    static class DatabaseUrlPresent implements Condition {
        @Override
        public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
            String url = context.getEnvironment().getProperty("DATABASE_URL");
            return url != null && !url.isBlank();
        }
    }

    @Bean
    @Primary
    public DataSource dataSource(Environment env) {
        String rawUrl = env.getProperty("DATABASE_URL").trim();
        log.info("Configurando DataSource desde DATABASE_URL (PostgreSQL).");

        // Normalizar esquema: postgres:// y postgresql:// -> jdbc:postgresql://
        String normalized = rawUrl
                .replaceFirst("^postgres://", "jdbc:postgresql://")
                .replaceFirst("^postgresql://", "jdbc:postgresql://");

        // Extraer credenciales embebidas en la URL (user:pass@host).
        String jdbcUrl = normalized;
        String username = env.getProperty("DB_USERNAME", "");
        String password = env.getProperty("DB_PASSWORD", "");

        try {
            URI uri = URI.create(normalized.replaceFirst("^jdbc:", ""));
            if (uri.getUserInfo() != null) {
                String[] creds = uri.getUserInfo().split(":", 2);
                if (creds.length == 2) {
                    username = creds[0];
                    password = creds[1];
                }
                // Reconstruir la URL sin credenciales.
                String cleanUrl = "jdbc:postgresql://%s:%d%s".formatted(
                        uri.getHost(),
                        uri.getPort() == -1 ? 5432 : uri.getPort(),
                        uri.getPath());
                jdbcUrl = cleanUrl;
            }
        } catch (IllegalArgumentException ex) {
            log.warn("No se pudo parsear DATABASE_URL, se usa tal cual: {}", ex.getMessage());
        }

        // Esquema dedicado (una sola BD, varios esquemas). Si DB_SCHEMA está
        // definido y la URL no trae currentSchema, se añade automáticamente.
        String schema = env.getProperty("DB_SCHEMA", "").trim();
        if (!schema.isEmpty() && !jdbcUrl.contains("currentSchema=")) {
            jdbcUrl += (jdbcUrl.contains("?") ? "&" : "?") + "currentSchema=" + schema;
        }

        // SSL obligatorio para Supabase si no viene especificado.
        if (!jdbcUrl.contains("sslmode=")) {
            jdbcUrl += (jdbcUrl.contains("?") ? "&" : "?") + "sslmode=require";
        }

        HikariDataSource ds = new HikariDataSource();
        ds.setJdbcUrl(jdbcUrl);
        ds.setUsername(username);
        ds.setPassword(password);
        ds.setDriverClassName("org.postgresql.Driver");
        ds.setMaximumPoolSize(env.getProperty("DB_POOL_SIZE", Integer.class, 5));
        ds.setPoolName("supabase-pool");
        return ds;
    }
}
