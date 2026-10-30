Rails.application.config.to_prepare do
  # Allow iframe embedding for partners
  if defined?(ApplicationController)
    ApplicationController.class_eval do
      after_action :allow_partner_iframe_embedding

      def allow_partner_iframe_embedding
        response.headers.delete('X-Frame-Options')
        response.headers['Content-Security-Policy'] = "frame-ancestors *"
        response.headers['Permissions-Policy'] = "keyboard-map=*"
      end
    end
  end

  if defined?(DashboardController)
    DashboardController.class_eval do
      after_action :allow_partner_iframe_embedding

      def allow_partner_iframe_embedding
        response.headers.delete('X-Frame-Options')
        response.headers['Content-Security-Policy'] = "frame-ancestors *"
        response.headers['Permissions-Policy'] = "keyboard-map=*"
      end
    end
  end

  if defined?(Enterprise::Api::V1::AccountsController)
    Enterprise::Api::V1::AccountsController.class_eval do
      skip_before_action :check_cloud_env, only: [:limits], raise: false

      def limits
        render json: { id: @account.id, limits: {} }, status: :ok
      end
    end
  end

  begin
    require 'captain/tools/http_tool' if defined?(Captain)
  rescue LoadError
  end

  if defined?(Captain::Tools::HttpTool)
    Captain::Tools::HttpTool.class_eval do
      unless method_defined?(:orig_execute_http_request)
        alias_method :orig_execute_http_request, :execute_http_request
        def execute_http_request(url, body, tool_context)
          resp = orig_execute_http_request(url, body, tool_context)
          resp.is_a?(String) ? resp.dup.force_encoding('UTF-8') : resp
        end
      end
    end
  end

  # Configure RubyLLM & Agents with OpenAI key & model
  key = ENV['CAPTAIN_OPEN_AI_API_KEY'] || ENV['OPENAI_API_KEY']
  if key.present?
    begin
      require 'ruby_llm'
      RubyLLM.configure do |c|
        c.openai_api_key = key
        c.model_registry_file = Rails.root.join('config/llm_models.json').to_s
        c.openai_protocol = :chat_completions
      end
    rescue => e
      Rails.logger.error "Failed to configure RubyLLM in limits_patch: #{e.message}"
    end

    begin
      require 'agents'
      Agents.configure do |c|
        c.openai_api_key = key
        c.default_model = ENV['CAPTAIN_OPEN_AI_MODEL'] || 'gpt-4o-mini'
        c.openai_protocol = :chat_completions
        c.model_registry_file = Rails.root.join('config/llm_models.json').to_s
      end
    rescue => e
      Rails.logger.error "Failed to configure Agents in limits_patch: #{e.message}"
    end
  end

  # Ensure Captain AI automatically processes incoming messages in Captain-connected inboxes
  if defined?(Enterprise::MessageTemplates::HookExecutionService)
    Enterprise::MessageTemplates::HookExecutionService.module_eval do
      unless method_defined?(:orig_trigger_templates)
        alias_method :orig_trigger_templates, :trigger_templates

        def trigger_templates
          if message.incoming? && inbox.captain_assistant.present? && !inbox.external_bot_active?
            # If conversation has no human assignee, ensure it is pending so Captain responds
            if conversation.assignee_id.blank? && !conversation.pending?
              conversation.update_columns(status: Conversation.statuses[:pending])
            end
          end
          orig_trigger_templates
        end
      end
    end
  end
end
