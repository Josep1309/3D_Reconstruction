function [e,erms,Ze,TTs] = Plane_fitting(XX,YY,ZZ,mask,fig)


    e=zeros(size(XX));
    
    if(nargin<5)
    fig = 800;
    end
    gc=figure(fig);hold off
    for i=1:size(XX,3)
        


        if(nargin<4 || isempty(mask))
            Ind = find(~isnan(XX(:,:,i,1)));
        else
            Ind = find(double((~isnan(XX(:,:,i,1))).*mask(:,:,i)));
        end


        x = XX(:,:,i);
        y = YY(:,:,i);
        z = ZZ(:,:,i);

        % Solution by Least square fitting
        % Z = Ax+By+C
        A= [x(Ind),y(Ind),ones(size(x(Ind)))];
        AA = A'*A;
        B = A'*z(Ind);
        TT = AA\B;
        TTs(i,:) = TT; 
        
        
        
        ze = (TT(1)*x+TT(2)*y+TT(3));
        ze2 = (TT(1)*x+TT(3));
        
        if(nargout>2)
            Ze(:,:,i)=ze;
        end
        % Distances between t
        e(:,:,i) = (TT(1)*x+TT(2)*y-1*z+TT(3))/sqrt(TT(1)^2+TT(2)^2+1);
%         medis = mean(abs(dis));
        
        
        m=e(:,:,i);
        ind = find(~isnan(m(:)));
        vecto = 1:50;
        
        if(~isempty(ind) && sum((i==vecto))>0)
            
        figure(gc), plot([x(ind(1)),x(ind(end))],[ze2(ind(1)) ze(ind(end))],'LineWidth',1),hold on    
%         figure(gc), plot([x(ind(1)),x(ind(end))],[ze2(ind(1)) ze(ind(end))],'LineWidth',1),hold on
        text(x(ind(1)),ze2(ind(1)),num2str(find((i==vecto))),'FontSize',6)
        end


    end
     plot(0:210,-46.4*ones(size(0:210)),'k','LineWidth',1)
     plot(0:210, 48.0*ones(size(0:210)),'k','LineWidth',1)
    
    
    ei = reshape(e,[size(e,1)*size(e,2) size(e,3)]);
    for i=1:size(ei,2)
        in1 = ~isnan(ei(:,i));
        erms(i) = sqrt(sum((ei(in1,i)-mean(ei(in1,i))).^2)/numel(ei(in1,i)));
    end


end